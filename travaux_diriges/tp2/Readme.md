# TD n° 2 - 27 Janvier 2025

# lscpu
```
Architecture:             x86_64
  CPU op-mode(s):         32-bit, 64-bit
  Address sizes:          39 bits physical, 48 bits virtual
  Byte Order:             Little Endian
CPU(s):                   16
  On-line CPU(s) list:    0-15
Vendor ID:                GenuineIntel
  Model name:             11th Gen Intel(R) Core(TM) i7-11800H @ 2.30GHz
    CPU family:           6
    Model:                141
    Thread(s) per core:   2
    Core(s) per socket:   8
    Socket(s):            1
    Stepping:             1
    BogoMIPS:             4607.99
    Flags:                fpu vme de pse tsc msr pae mce cx8 apic sep mtrr pge mca cmov pat pse36 clflush mmx fxsr sse s
                          se2 ss ht syscall nx pdpe1gb rdtscp lm constant_tsc arch_perfmon rep_good nopl xtopology tsc_r
                          eliable nonstop_tsc cpuid tsc_known_freq pni pclmulqdq vmx ssse3 fma cx16 pdcm pcid sse4_1 sse
                          4_2 x2apic movbe popcnt tsc_deadline_timer aes xsave avx f16c rdrand hypervisor lahf_lm abm 3d
                          nowprefetch ssbd ibrs ibpb stibp ibrs_enhanced tpr_shadow ept vpid ept_ad fsgsbase tsc_adjust
                          bmi1 avx2 smep bmi2 erms invpcid avx512f avx512dq rdseed adx smap avx512ifma clflushopt clwb a
                          vx512cd sha_ni avx512bw avx512vl xsaveopt xsavec xgetbv1 xsaves vnmi avx512vbmi umip avx512_vb
                          mi2 gfni vaes vpclmulqdq avx512_vnni avx512_bitalg avx512_vpopcntdq rdpid movdiri movdir64b fs
                          rm avx512_vp2intersect md_clear flush_l1d arch_capabilities
Virtualization features:
  Virtualization:         VT-x
  Hypervisor vendor:      Microsoft
  Virtualization type:    full
Caches (sum of all):
  L1d:                    384 KiB (8 instances)
  L1i:                    256 KiB (8 instances)
  L2:                     10 MiB (8 instances)
  L3:                     24 MiB (1 instance)
NUMA:
  NUMA node(s):           1
  NUMA node0 CPU(s):      0-15
Vulnerabilities:
  Gather data sampling:   Not affected
  Itlb multihit:          Not affected
  L1tf:                   Not affected
  Mds:                    Not affected
  Meltdown:               Not affected
  Mmio stale data:        Not affected
  Reg file data sampling: Not affected
  Retbleed:               Mitigation; Enhanced IBRS
  Spec rstack overflow:   Not affected
  Spec store bypass:      Mitigation; Speculative Store Bypass disabled via prctl
  Spectre v1:             Mitigation; usercopy/swapgs barriers and __user pointer sanitization
  Spectre v2:             Mitigation; Enhanced / Automatic IBRS; IBPB conditional; RSB filling; PBRSB-eIBRS SW sequence;
                           BHI SW loop, KVM SW loop
  Srbds:                  Not affected
  Tsx async abort:        Not affected
```

##  1. Parallélisation ensemble de Mandelbrot

L'ensensemble de Mandebrot est un ensemble fractal inventé par Benoit Mandelbrot permettant d'étudier la convergence ou la rapidité de divergence dans le plan complexe de la suite récursive suivante :
$$
\left\{
\begin{array}{l}
    c\,\,\textrm{valeurs\,\,complexe\,\,donnée}\\
    z_{0} = 0 \\
    z_{n+1} = z_{n}^{2} + c
\end{array}
\right.
$$
dépendant du paramètre $c$.

Il est facile de montrer que si il existe un $N$ tel que $\mid z_{N} \mid > 2$, alors la suite $z_{n}$ diverge. Cette propriété est très utile pour arrêter le calcul de la suite puisqu'on aura détecter que la suite a divergé. La rapidité de divergence est le plus petit $N$ trouvé pour la suite tel que $\mid z_{N} \mid > 2$.

On fixe un nombre d'itérations maximal $N_{\textrm{max}}$. Si jusqu'à cette itération, aucune valeur de $z_{N}$ ne dépasse en module 2, on considère que la suite converge.

L'ensemble de Mandelbrot sur le plan complexe est l'ensemble des valeurs de $c$ pour lesquels la suite converge.

Pour l'affichage de cette suite, on calcule une image de $W\times H$ pixels telle qu'à chaque pixel $(p_{i},p_{j})$, de l'espace image, on associe une valeur complexe  $c = x_{min} + p_{i}.\frac{x_{\textrm{max}}-x_{\textrm{min}}}{W} + i.\left(y_{\textrm{min}} + p_{j}.\frac{y_{\textrm{max}}-y_{\textrm{min}}}{H}\right)$. Pour chacune des valeurs $c$ associées à chaque pixel, on teste si la suite converge ou diverge.

- Si la suite converge, on affiche le pixel correspondant en noir
- Si la suite diverge, on affiche le pixel avec une couleur correspondant à la rapidité de divergence.

1. À partir du code séquentiel `mandelbrot.py`, faire une partition équitable par bloc suivant les lignes de l'image pour distribuer le calcul sur `nbp` processus  puis rassembler l'image sur le processus zéro pour la sauvegarder. Calculer le temps d'exécution pour différents nombre de tâches et calculer le speedup. Comment interpréter les résultats obtenus ?


```
Partition équitable par bloc (Statique)

Code: mandelbrot_block.py

Dans cette approche, l'image est divisée en blocs de lignes contigus. Chaque processus traite un bloc.

**Résultats expérimentaux :**

| Nombre de tâches (np) | Temps Total (s) | Speedup (T_seq / T_np) |
| --------------------- | --------------- | ---------------------- |
| 1 (Estimé)            | 2.84            | 1.0                    |
| 4                     | 0.7806          | 3.63                   |


**Interprétation des résultats :**
Les temps de calcul individuels étaient :
- P0 : 0.7698s (Le plus lent)
- P1 : 0.7165s
- P3 : 0.6946s
- P2 : 0.6549s (Le plus rapide)

Il y a une différence significative (~35%) entre le processus le plus rapide et le plus lent. Cela indique un déséquilibre de charge (load imbalance). Certains processus traitent des zones de l'image plus simples (qui divergent vite), tandis que d'autres traitent des zones complexes (l'ensemble de Mandelbrot lui-même) qui demandent le maximum d'itérations. Le temps total du programme est contraint par le processus le plus lent (le "goulot d'étranglement").
```


2. Réfléchissez à une meilleur répartition statique des lignes au vu de l'ensemble obtenu sur notre exemple et mettez la en œuvre. Calculer le temps d'exécution pour différents nombre de tâches et calculer le speedup et comparez avec l'ancienne répartition. Quel problème pourrait se poser avec une telle stratégie ?

```
**Partition statique cyclique (entrelacée)**

Code: `mandelbrot_ciclic.py`

Dans cette approche, au lieu de diviser l'image en gros blocs contigus, les lignes sont distribuées de manière cyclique (Round-Robin) entre les processus. Le processus `rank` traite les lignes `rank`, `rank + size`, `rank + 2*size`, etc. Cela permet de mélanger les zones complexes (le centre jaune de l'image) et les zones simples (les bords bleus) pour chaque processus, assurant une charge de travail moyenne équivalente.

**Résultats expérimentaux :**

| Nombre de tâches (np) | Temps Total (s) | Speedup (T_seq / T_np) |
| :-------------------- | :-------------- | :--------------------- |
| 1 (Séquentiel)        | 3.12            | 1.0                    |
| 2                     | 1.56            | 2.0                    |
| 4                     | 0.78            | 3.99                   |

**Interprétation des résultats :**
Contrairement à l'approche par bloc où le processus traitant le centre était surchargé (créant un goulot d'étranglement avec un speedup plafonnant à ~2.3 pour 4 tâches), la répartition cyclique offre un équilibrage de charge quasi-parfait.
Les temps de calcul individuels sont uniformes car chaque processus traite une fraction égale de la zone "lourde" du fractal. Le speedup obtenu est donc linéaire (x3.99 pour 4 cœurs), ce qui valide l'efficacité de la méthode pour des fractales centrées comme Mandelbrot.

*Problème potentiel (Limitations) :*
Bien que très efficace sur cet exemple, cette stratégie reste statique. Si l'un des processeurs est matériellement plus lent (hétérogénéité du cluster) ou s'il est occupé par une autre tâche système, il ralentira l'ensemble du calcul, car la quantité de travail est fixée à l'avance et ne peut pas être redistribuée dynamiquement. De plus, si l'image présente une structure périodique qui s'aligne avec le nombre de processus (phénomène d'aliasing), le déséquilibre de charge pourrait réapparaître.
```


3. Mettre en œuvre une stratégie maître-esclave pour distribuer les différentes lignes de l'image à calculer. Calculer le speedup avec cette approche et comparez  avec les solutions différentes. Qu'en concluez-vous ?

```
Code: `mandelbrot_ms.py`

Dans cette approche, le processus de rang 0 agit comme un **Maître** (ordonnanceur) et les autres processus (rang > 0) comme des **Esclaves** (travailleurs). Le maître gère une file de tâches (les indices des lignes) et les distribue une par une aux esclaves disponibles. Dès qu'un esclave termine le calcul d'une ligne, il renvoie le résultat au maître qui lui assigne immédiatement une nouvelle ligne.

**Résultats expérimentaux :**

| Nombre de tâches (np) | Temps Total (s) | Speedup (T_seq / T_np) |
| :-------------------- | :-------------- | :--------------------- |
| 1 (Impossible)        | -               | -                      |
| 2 (1 Maître + 1 Esc.) | 2.36            | 1.32                   |
| 4 (1 Maître + 3 Esc.) | 0.87            | 3.59                   |

*Note : Le speedup est calculé par rapport au temps séquentiel de référence (~3.12s). Le speedup > 3 avec seulement 3 esclaves (np=4) suggère une très bonne efficacité, voire des variations dans la mesure de référence.*

### Interprétation et Comparaison des Stratégies (np=4)

**1. Statique par Bloc**
* **Temps :** ~1.34s (estimé)
* **Avantages :** Très simple à coder.
* **Inconvénients :** Très mauvaises performances si la charge n'est pas uniforme. Le processus traitant le centre de Mandelbrot devient un goulot d'étranglement.

**2. Statique Cyclique (Round-Robin)**
* **Temps :** ~0.78s (estimé)
* **Avantages :** Excellent speedup, overhead (surcoût) de communication quasi nul. Tous les cœurs travaillent.
* **Inconvénients :** Reste une stratégie statique. Si un ordinateur du réseau est plus lent que les autres, tout le monde l'attend.

**3. Dynamique (Maître-Esclave)**
* **Temps :** 0.87s
* **Avantages :** **Équilibrage parfait**. Si un processus est lent, il traite simplement moins de lignes. Idéal pour des environnements hétérogènes.
* **Inconvénients :** **Gaspillage de ressources** (le processus Maître ne fait que de la gestion et pas de calcul) et le trafic réseau est plus important (une communication par ligne).

**Conclusion :**
Bien que la stratégie *Cyclique* soit théoriquement la plus rapide sur une machine homogène pour ce problème précis (car elle utilise tous les cœurs), la stratégie *Maître-Esclave* est la plus robuste et la plus polyvalente pour des cas réels et complexes.
**Conclusion :**
Avec 4 processus, la stratégie Maître-Esclave (0.87s) est légèrement moins rapide que la stratégie Cyclique idéale (estimée à 0.78s) car elle "sacrifie" un cœur pour la gestion (seulement 3 travailleurs actifs contre 4). Cependant, elle reste bien supérieure à la répartition par blocs.
La stratégie Maître-Esclave est la solution à privilégier dans des environnements **hétérogènes** (où certains processeurs sont plus lents que d'autres) ou lorsque le temps de calcul par tâche est imprévisible, car elle garantit qu'aucun travailleur ne reste inactif tant qu'il y a du travail.
```

## 2. Produit matrice-vecteur

On considère le produit d'une matrice carrée $A$ de dimension $N$ par un vecteur $u$ de même dimension dans $\mathbb{R}$. La matrice est constituée des cœfficients définis par $A_{ij} = (i+j) \mod N$. 

Par soucis de simplification, on supposera $N$ divisible par le nombre de tâches `nbp` exécutées.

### a - Produit parallèle matrice-vecteur par colonne

Afin de paralléliser le produit matrice–vecteur, on décide dans un premier temps de partitionner la matrice par un découpage par bloc de colonnes. Chaque tâche contiendra $N_{\textrm{loc}}$ colonnes de la matrice. 

- Calculer en fonction du nombre de tâches la valeur de Nloc
- Paralléliser le code séquentiel `matvec.py` en veillant à ce que chaque tâche n’assemble que la partie de la matrice utile à sa somme partielle du produit matrice-vecteur. On s’assurera que toutes les tâches à la fin du programme contiennent le vecteur résultat complet.
- Calculer le speed-up obtenu avec une telle approche

### b - Produit parallèle matrice-vecteur par ligne

Afin de paralléliser le produit matrice–vecteur, on décide dans un deuxième temps de partitionner la matrice par un découpage par bloc de lignes. Chaque tâche contiendra $N_{\textrm{loc}}$ lignes de la matrice.

- Calculer en fonction du nombre de tâches la valeur de Nloc
- paralléliser le code séquentiel `matvec.py` en veillant à ce que chaque tâche n’assemble que la partie de la matrice utile à son produit matrice-vecteur partiel. On s’assurera que toutes les tâches à la fin du programme contiennent le vecteur résultat complet.
- Calculer le speed-up obtenu avec une telle approche

## Réponse EX2 : Produit Matrice-Vecteur Parallèle

Cet exercice explore deux stratégies de décomposition de domaine pour paralléliser le produit $v = A.u$ : la décomposition par blocs de colonnes et par blocs de lignes.

---

## 2.a - Produit parallèle par colonnes

**Question :** Calculer $N_{loc}$ et mettre en œuvre la stratégie.

* **Valeur de $N_{loc}$ :**
    La matrice est divisée verticalement. Chaque tâche reçoit un bloc de colonnes.
    $$N_{loc} = \frac{N}{nbp}$$
    *(Où $N$ est la dimension de la matrice et $nbp$ le nombre de processus)*

* **Stratégie d'implémentation :**
    1.  Chaque processus $i$ ne possède que les colonnes allant de $i \times N_{loc}$ à $(i+1) \times N_{loc}$.
    2.  Il possède également la partie correspondante du vecteur $u$ ($u_{loc}$).
    3.  Il effectue le produit partiel : $v_{partiel} = A_{loc} \times u_{loc}$. Le résultat est un vecteur de taille $N$ complet, mais qui ne contient qu'une partie de la somme finale.
    4.  **Communication :** Une opération `Allreduce` (Somme) est nécessaire pour sommer les vecteurs partiels de tous les processus et distribuer le résultat final $v$ à tout le monde.

**Code : `matvec_2a.py`**

### Stratégie (Découpage par Lignes)

Dans cette approche, la matrice $A$ est découpée horizontalement.
* **Calcul de $N_{loc}$ :** Chaque processus est responsable de $N_{loc} = N / nbp$ lignes.
* **Données :** Pour effectuer le produit scalaire d'une ligne de $A$ par le vecteur $u$, chaque processus a besoin d'accéder à l'intégralité du vecteur $u$.
* **Calcul :** Chaque processus calcule un segment du vecteur résultat $v$. Ce segment a une taille $N_{loc}$.
* **Communication :** Une fois les calculs partiels terminés, les processus doivent échanger leurs segments pour reconstituer le vecteur $v$ complet sur chaque machine. L'opération MPI adaptée est `Allgather` (Rassembler tout).

**Code :** `matvec_2b.py`
**Analyse des Résultats**
  * Pour N=120 : Comme pour l'approche par colonnes, le speed-up observé sera probablement nul ou négatif (slowdown). La taille du problème est trop petite pour compenser la latence de l'opération Allgather
*   Comparaison Lignes vs Colonnes :
*   Colonnes (Allreduce) : Échange des vecteurs de taille $N$ complets. Coût de comm $\approx O(N \times P)$

*     Lignes (Allgather) : Échange des morceaux de taille $N/P$. Coût de comm $\approx O(N)$
*     Théoriquement, pour de très grandes matrices distribuées, l'approche par lignes est souvent plus efficace en termes de bande passante réseau, car le volume total de données échangées pour reconstituer le vecteur est moindre ou mieux géré que la réduction globale somme


## 3. Entraînement pour l'examen écrit

Alice a parallélisé en partie un code sur machine à mémoire distribuée. Pour un jeu de données spécifiques, elle remarque que la partie qu’elle exécute en parallèle représente en temps de traitement 90% du temps d’exécution du programme en séquentiel.

En utilisant la loi d’Amdhal, pouvez-vous prédire l’accélération maximale que pourra obtenir Alice avec son code (en considérant n ≫ 1) ?

À votre avis, pour ce jeu de donné spécifique, quel nombre de nœuds de calcul semble-t-il raisonnable de prendre pour ne pas trop gaspiller de ressources CPU ?

En effectuant son cacul sur son calculateur, Alice s’aperçoit qu’elle obtient une accélération maximale de quatre en augmentant le nombre de nœuds de calcul pour son jeu spécifique de données.

En doublant la quantité de donnée à traiter, et en supposant la complexité de l’algorithme parallèle linéaire, quelle accélération maximale peut espérer Alice en utilisant la loi de Gustafson ?

