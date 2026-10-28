# Viva Questions and Answers

### 1. What is a node?
A node is a device or point in a network that can send, receive, or forward data. In this simulator, letters A through H identify nodes.

### 2. What is a link?
A link is a connection between two nodes. The configuration records whether it is available and how likely delivery is in each direction.

### 3. What is routing?
Routing is choosing a path through a network so data can get from a source node to a destination node.

### 4. What is a routing table?
A routing table is information a node uses to choose where to send data next. Here each entry stores a destination, an estimated cost, and a next hop.

### 5. What is a hop?
A hop is one link traversal from one node to a directly connected node. A path A-B-D contains two hops.

### 6. What is Hop Count?
Hop Count assigns cost 1 to every available link. The route with the fewest links has the lowest cost, regardless of link reliability.

### 7. What is ETX?
ETX, or Expected Transmission Count, estimates the number of transmissions needed for successful delivery. For the model in this project, a link's ETX is `1 / (forward delivery probability * reverse delivery probability)`.

### 8. Why does ETX use forward and reverse delivery probabilities?
Wireless delivery often needs the data packet to arrive and an acknowledgment to return. If either direction is unreliable, retransmissions can be needed. The probability product models success in both directions under the project's assumptions.

### 9. What is Distance Vector routing?
Each node keeps route-cost estimates and learns from its direct neighbors' advertised vectors. It updates routes using the neighbor's estimate plus the cost of the connecting link.

### 10. What is the Bellman–Ford algorithm?
Bellman–Ford repeatedly improves distance estimates by considering routes through neighboring nodes. In this simulator each node applies the recurrence using neighbor advertisements rather than a centralized graph solver.

### 11. What is Link State routing?
Each node advertises information about its own links. Flooding shares that information, after which every node calculates routes from its own topology database.

### 12. What is Dijkstra's algorithm?
Dijkstra finds minimum-cost paths from one starting node when edge costs are non-negative. Each simulated router runs its own Dijkstra computation over its local Link State database.

### 13. What is convergence?
Convergence is when routing information stops changing and routers agree on stable routes for the current modeled topology. The output counts synchronous update/flooding rounds, not seconds.

### 14. What is a link failure?
A link failure means a connection is no longer available for routing. The simulator removes it from route calculations and lets the protocols update their information.

### 15. What is count to infinity?
It is a Distance Vector problem where routers mistakenly believe one another still has a route to a failed destination. Their estimated costs can increase repeatedly until a protocol limit is reached.

### 16. What are split horizon and poison reverse?
Split horizon does not advertise a route back toward the neighbor from which it was learned. Poison reverse advertises that route back with infinite cost. Both reduce certain two-node loop scenarios.

### 17. Why might a longer route be better?
A route with more links can use reliable links, while a shorter route may contain a very lossy link. The simulation's ETX metric can prefer the longer path if its total expected transmission cost is lower.

### 18. How are control messages counted?
One Distance Vector message is a complete vector sent over one directed active link during a round. One Link State message is one LSA copy sent over one directed link. They count transmissions, not bytes or actual network packets.

### 19. What are the limitations of this simulator?
It uses a small fixed undirected network, fixed probabilities, and synchronous rounds. It does not model real timers, delays, traffic, packet losses during protocol exchange, hardware, or elapsed-time convergence.

### 20. What conclusions can be drawn from the actual experimental results?
In the configured A-to-D experiment, Hop Count chooses the two-hop A-B-D path, but ETX chooses the three-hop A-E-F-D path with lower computed ETX. The A-B failure causes a detour and recovery restores the Hop Count path. These are results for this configuration, not a claim that one protocol or metric is always best.
