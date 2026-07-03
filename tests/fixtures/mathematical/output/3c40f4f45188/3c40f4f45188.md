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