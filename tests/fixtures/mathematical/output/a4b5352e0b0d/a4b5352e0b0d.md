---
{}
---

## 2.2 Wasserstein distance

The Wasserstein distance is a distance function between probability distributions defined on a given metric space. Let $\sigma$ and $\mu$ be two probability distributions on a metric space $M$ equipped with a ground distance $d$, such as the Euclidean distance.
**Definition 1.** The $L^p$-Wasserstein distance for $p \in [1, \infty)$ is defined as
$$W_p(\sigma, \mu) := \left( \inf_{\gamma \in \Gamma(\sigma, \mu)} \int_{M \times M} d(x,y)^p \,d\gamma(x,y) \right)^{\frac{1}{p}}, \quad (1)$$
where $\Gamma(\sigma, \mu)$ is the set of all transportation plans $\gamma \in \Gamma(\sigma, \mu)$ over $M \times M$ with marginals $\sigma$ and $\mu$ on the first and second factors, respectively.

The Wasserstein distance satisfies the axioms of a metric, provided that $d$ is a metric (see the monograph of Villani [44], chapter 6, for a proof). Throughout the paper, we will focus on the distance for $p = 1$ and we will refer to the $L^1$-Wasserstein distance when mentioning the Wasserstein distance, unless noted otherwise.

The Wasserstein distance is linked to the optimal transport problem [44], where the aim is to find the most “inexpensive” way, in terms of the ground distance, to transport all the probability mass from distribution $\sigma$ to match distribution $\mu$. An intuitive illustration can be made for the 1-dimensional case, where the two probability distributions can be imagined as piles of dirt or sand. The Wasserstein distance, sometimes also referred to as the earth mover’s distance [34], can be interpreted as the minimum effort required to move the content of the first pile to reproduce the second pile.

In this paper, we deal with finite sets of node embeddings and not with continuous probability distributions. Therefore, we can reformulate the Wasserstein distance as a sum rather than an integral, and use the matrix notation commonly encountered in the optimal transport literature [34] to represent the transportation plan. Given two sets of vectors $X \in \mathbb{R}^{n \times m}$ and $X' \in \mathbb{R}^{n' \times m}$, we can equivalently define the Wasserstein distance between them as
$$W_1(X, X') := \min_{P \in \Gamma(X,X')} \langle P, M \rangle. \quad (2)$$
Here, $M$ is the distance matrix containing the distances $d(x, x')$ between each element $x$ of $X$ and $x'$ of $X'$, $P \in \Gamma$ is a transport matrix (or joint probability), and $\langle \cdot, \cdot \rangle$ is the Frobenius dot product. The transport matrix $P$ contains the fractions that indicate how to transport the values from $X$ to $X'$ with the minimal total transport effort. Because we assume that the total mass to be transported equals 1 and is evenly distributed across the elements of $X$ and $X'$, the row and column values of $P$ must sum up to $1/n$ and $1/n'$, respectively.

## 3 Wasserstein distance on graphs

The unsatisfactory nature of the aggregation step of current $\mathcal{R}$-Convolution graph kernels, which may mask important substructure differences by averaging, motivated us to have a finer distance measure between structures and their components. In parallel, recent advances in optimisation solutions for faster computation of the optimal transport problem inspired us to consider this framework for the problem of graph classification. Our method relies on the following steps: (1) transform each graph into a set of node embeddings, (2) measure the Wasserstein distance between each pair of graphs, and (3) compute a similarity matrix to be used in the learning algorithm. Figure 1 illustrates the first two steps, and Algorithm 1 summarises the whole procedure. We start by defining an embedding scheme and illustrate how we integrate embeddings in the Wasserstein distance.

**Definition 2** (Graph Embedding Scheme). Given a graph $G = (V, E)$, a graph embedding scheme $f : G \to \mathbb{R}^{|V| \times m}$, $f(G) = X_G$ is a function that outputs a fixed-size vectorial representation for each node in the graph. For each $v_i \in V$, the $i$-th row of $X_G$ is called the node embedding of $v_i$.

Note that Definition 2 permits treating node labels, which are categorical attributes, as one-dimensional attributes with $m = 1$.

**Definition 3** (Graph Wasserstein Distance). Given two graphs $G = (V, E)$ and $G' = (V', E')$, a graph embedding scheme $f : G \to \mathbb{R}^{|V| \times m}$ and a ground distance $d : \mathbb{R}^m \times \mathbb{R}^m \to \mathbb{R}$, we define the Graph Wasserstein Distance (GWD) as
$$D_W^f (G, G') := W_1(f(G), f(G')). \quad (3)$$

3