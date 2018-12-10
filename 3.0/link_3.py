import queue
import threading
import time

## Implements a link layer frame
# Needed to tell the network layer the type of the payload
class LinkFrame:
    ## packet encoding lengths
    type_S_length = 1

    ##@param type_S: type of packet in the frame - what higher layer should handle it
    # @param data_S: frame payload
    def __init__(self, type_S, data_S):
        self.type_S = type_S
        self.data_S = data_S

    ## called when printing the object
    def __str__(self):
        return self.to_byte_S()

    ## convert frame to a byte string for transmission over links
    def to_byte_S(self):
        byte_S = ''
        if self.type_S == 'MPLS':
            byte_S += 'M' # of length type_S_length
        elif self.type_S == 'Network':
            byte_S += 'N'
        else:
            raise('%s: unknown type_S option: %s' %(self, self.type_S))
        byte_S += self.data_S
        return byte_S

    ## extract a frame object from a byte string
    # @param byte_S: byte string representation of the packet
    @classmethod
    def from_byte_S(self, byte_S):
        type_S = byte_S[0 : self.type_S_length]
        if type_S == 'M':
            type_S = 'MPLS'
        elif type_S == 'N':
            type_S = 'Network'
        else:
            raise('%s: unknown type_S field: %s' % (self, type_S))
        data_S = byte_S[self.type_S_length: ]
        return self(type_S, data_S)



## An abstraction of a link between router interfaces
class Link:

    ## creates a link between two objects by looking up and linking node interfaces.
    # @param node_1: node from which data will be transfered
    # @param node_1_intf: number of the interface on that node
    # @param node_2: node to which data will be transfered
    # @param node_2_intf: number of the interface on that node
    def __init__(self, node_1, node_1_intf, node_2, node_2_intf):
        self.node_1 = node_1
        self.node_1_intf = node_1_intf
        self.node_2 = node_2
        self.node_2_intf = node_2_intf
        print('Created link %s' % self.__str__())

    ## called when printing the object
    def __str__(self):
        return 'Link %s-%d - %s-%d' % (self.node_1, self.node_1_intf, self.node_2, self.node_2_intf)

    ##transmit a packet between interfaces in each direction
    def tx_pkt(self):
        for (node_a, node_a_intf, node_b, node_b_intf) in \
        [(self.node_1, self.node_1_intf, self.node_2, self.node_2_intf),
         (self.node_2, self.node_2_intf, self.node_1, self.node_1_intf)]:
            #print(str(node_a))
            #print(node_a_intf)
            intf_a = node_a.intf_L[node_a_intf]
            intf_b = node_b.intf_L[node_b_intf]
            if intf_a.out_queue.empty():
                continue #continue if no packet to transfer
            #otherwise try transmitting the packet
            try:
                #check if the interface is free to transmit a packet
                if intf_a.next_avail_time <= time.time():
                    #transmit the packet
                    pkt_S = intf_a.get('out')
                    intf_b.put(pkt_S, 'in')
                    #update the next free time of the interface according to serialization delay
                    pkt_size = len(pkt_S)*8 #assuming each character is 8 bits
                    intf_a.next_avail_time = time.time() + pkt_size/intf_a.capacity

                    intf_a_hp_pkts = 0              # A counter for how many high priority packets are in the queue
                    intf_a_lp_pkts = 0              # A counter for how many low priority packets are in the queue
                    priority = 0                    # Initialize priority field here for later scope usage
                    hp_queue = queue.Queue(0)       # A temporary queue to organize high priority packets before low ones
                    lp_queue = queue.Queue(0)       # A temporary queue to organize low priority packets after high ones

                    for i in range(intf_a.out_queue.qsize()):
                        temp = intf_a.get('out')    #temporarily take out the next packet waiting

                        if(temp[0] is "N" or "M"):  #if the packet has a label, then the priority is in position 6
                            priority = int(temp[6])
                        else:                       #else the priority is in position 5
                            priority = int(temp[5])

                        if priority is 1:           #if the priority is 1, then it is of high priority
                            intf_a_hp_pkts += 1
                            hp_queue.put(temp)
                        else:                       #else it is of low priority
                            intf_a_lp_pkts += 1
                            lp_queue.put(temp)

                    while not hp_queue.empty():     #put the high priority packets in the queue first
                        intf_a.put(hp_queue.get(), 'out')

                    while not lp_queue.empty():     #then put the low priority packets back
                        #print("Am i stuck in the lp_queue while loop?")
                        intf_a.put(lp_queue.get(), 'out')

                    print('%s: transmitting frame "%s" on %s %s -> %s %s \n' \
                          ' - seconds until the next available time %f\n' \
                          ' - queue size %d\n' \
                          ' - number of high priority packets %d\n' \
                          ' - number of low priority packets %d\n'
                          % (self, pkt_S, node_a, node_a_intf, node_b, node_b_intf, intf_a.next_avail_time - time.time(), intf_a.out_queue.qsize(), intf_a_hp_pkts, intf_a_lp_pkts))
                # uncomment the lines below to see waiting time until next transmission
#                 else:
#                     print('%s: waiting to transmit packet on %s %s -> %s, %s for another %f milliseconds' % (self, node_a, node_a_intf, node_b, node_b_intf, intf_a.next_avail_time - time.time()))
            except queue.Full:
                print('%s: packet lost' % (self))
                pass


## An abstraction of the link layer
class LinkLayer:

    def __init__(self):
        ## list of links in the network
        self.link_L = []
        self.stop = False #for thread termination

    ## called when printing the object
    def __str__(self):
        return 'Network'

    ##add a Link to the network
    def add_link(self, link):
        self.link_L.append(link)

    ##transfer a packet across all links
    def transfer(self):
        for link in self.link_L:
            link.tx_pkt()

    ## thread target for the network to keep transmitting data across links
    def run(self):
        print (threading.currentThread().getName() + ': Starting')
        while True:
            #transfer one packet on all the links
            self.transfer()
            #terminate
            if self.stop:
                print (threading.currentThread().getName() + ': Ending')
                return
