# OCR Pipeline Output

Generated: 2026-07-02T23:01:23.541096+00:00
PDFs processed: 2
Total pages: 2

---

---
{}
---

[p. 13]

**Lemma 1.** If a transportation plan $\gamma$ with transport matrix $P$ is optimal in the sense of Definition 1 for distances $d_{\text{Ham}}$ between embeddings obtained with $f^H_{WL}$, then it is also optimal for the discrete distances $d_{\text{disc}}$ between the $H$-th iteration values obtained with the Weisfeiler–Lehman procedure.

**Proof.** See Appendix A.2.

**Lemma 2.** If a transportation plan $\gamma$ with transport matrix $P$ is optimal in the sense of Definition 1 for distances $d_{\text{Ham}}$ between embeddings obtained with $f^H_{WL}$, then it is also optimal for distances $d_{\text{Ham}}$ between embeddings obtained with $f^{H-1}_{WL}$.

**Proof.** See Appendix A.3.

Therefore, we postulate that the Wasserstein distance between categorical WL node embeddings is a conditional negative definite function.

**Theorem 2.** $D^{f_{WL}}_{W}(\cdot, \cdot)$ is a conditional negative definite function.

**Proof.** See Appendix A.4.

**Proof of Theorem 1.** **Theorem 2** in light of **Proposition 2** implies that the WWL kernel of **Definition 5** is positive definite for all $\lambda > 0$. $\square$

We will now consider the case of the definiteness of kernels in the continuous setting.

### A.1.2 The case of continuous embeddings

On one hand, in the categorical case, we proved the positive definiteness of our kernel. On the other hand, the continuous case is considerably harder to tackle. We conjecture that, under certain conditions, the same might hold for continuous features. Although we do not have a formal proof yet, in what follows, we discuss arguments to support this conjecture, which seems to agree with our empirical findings.$^3$

The curvature of the metric space induced by the Wasserstein metric for a given ground distance plays an important role. First, we need to define Alexandrov spaces.

**Definition 7** (Alexandrov space). Given a metric space and a real number $k$, the space is called an Alexandrov space if its sectional curvature is $\geq k$.

Roughly speaking, the curvature indicates to what extent a geodesic triangle will be deformed in the space. The case of $k = 0$ is special as no distortion is happening here—hence, spaces that satisfy this property are called flat. The concept of Alexandrov spaces is required in the following proposition, taken from a theorem by Feragen et al. [11], which shows the relationship between a kernel and its underlying metric space.

**Proposition 3.** The geodesic Gaussian kernel (i.e., $q = 2$ in Equation 13) is positive definite for all $\lambda > 0$ if and only if the underlying metric space $(X, d)$ is flat in the sense of Alexandrov, i.e., if any geodesic triangle in $X$ can be isometrically embedded in a Euclidean space.

However, it is unlikely that the space induced by the Wasserstein distance is locally flat, as not even the geodesics (i.e., a generalisation of the shortest path to arbitrary metric spaces) between graph embeddings are necessarily unique, as we subsequently show. Hence, we use the geodesic Laplacian kernel instead of the Gaussian one because it poses less strict requirements on the induced space, as stated in **Proposition 2**. Specifically, the metric used in the kernel function needs to be cnd. We cannot directly prove this yet, but we can prove that the converse is not true. To this end, we first notice that the metric space induced by the GWD, which we refer to as $X$, does not have a curvature that is bounded from above.

**Definition 8.** A metric space $(X, d)$ is said to be CAT($k$) if its curvature is bounded by some real number $k > 0$ from above. This can also be seen as a “relaxed” definition, or generalisation, of a Riemannian manifold.

**Theorem 3.** $X$ is not in CAT($k$) for any $k > 0$, meaning that its curvature is not bounded by any $k > 0$ from above.

$^3$We observe that for all considered data sets, after standardisation of the input features before the embedding scheme, GWD matrices are conditional negative definite.

---

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