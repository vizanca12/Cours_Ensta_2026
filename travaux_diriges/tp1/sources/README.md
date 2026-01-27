
# TD1

`pandoc -s --toc README.md --css=./github-pandoc.css -o README.html`

## lscpu

*lscpu donne des infos utiles sur le processeur : nb core, taille de cache :*

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


## Produit matrice-matrice

### Effet de la taille de la matrice

  n            | MFlops
---------------|--------
1024 (origine) | 380.227
               |
1023           | 666.24
               |
1025           | 521.348

n = 1024 : bien que puissance de 2, la taille provoque des conflits de cache (mauvaise réutilisation des lignes de cache), ce qui pénalise fortement les accès mémoire performances faibles.

n = 1023 : taille non multiple des tailles de cache → meilleure dispersion des accès mémoire, moins de conflits → meilleure performance.

n = 1025 : toujours désaligné, mais la taille légèrement plus grande augmente la pression mémoire, ce qui dégrade un peu les performances par rapport à 1023.


### Permutation des boucles

Le code est compilé via le Makefile en mode optimisé (sans DEBUG=yes). Le compilateur C++ utilise la norme C++14 avec les options -O2 pour activer les optimisations et -march=native pour générer du code adapté au processeur de la machine. Les avertissements sont activés avec -Wall.

`make TestProduct.exe && ./TestProduct.exe 1024`


  ordre           | time    | MFlops  | MFlops(n=2048)
------------------|---------|---------|----------------
i,j,k (origine)   |5.49997|390.454|trop
j,i,k             |5.09872|421.181|trop
i,k,j             |7.66966|279.997|trop
k,i,j             |6.66910|322.005|trop
j,k,i             |0.80791|2658.05|trop
k,j,i             |1.21450|1768.20|trop


Boucle i = plus interne dans les opérations
L'ordre des boucles j, k, i obtient le meilleur temps (0.8s) car il optimise la gestion de la mémoire cache en respectant la localité spatiale des données. Dans cette configuration, la boucle la plus interne parcourt les adresses mémoires de façon contiguë (les unes à la suite des autres), ce qui permet de rentabiliser chaque chargement de ligne de cache depuis la RAM.

À l'inverse, les versions plus lentes (comme l'originale en 5.5s) effectuent des accès dispersés avec de grands sauts en mémoire. Cela provoque de nombreux défauts de cache ("cache misses"), forçant le processeur à attendre continuellement que les données arrivent de la mémoire principale, ce qui ralentit considérablement le calcul.



### OMP sur la meilleure boucle

`make TestProductMatrix.exe && OMP_NUM_THREADS=8 ./TestProductMatrix 1024`

  OMP_NUM         | time  | time(n=512) | time(n=2048)  | time(n=4096)
------------------|---------|----------------|----------------|---------------
1                 |0.65017|0.0643876|5.58825|trop
2                 |0.612339|0.063659|4.70999|trop
3                 |0.614302|0.067091|4.75037|trop
4                 |0.600455|0.0640106|5.435|trop
5                 |0.622752|0.0625432|5.43599|trop
6                 |0.645694|0.070363|5.67759|trop
7                 |0.620639|0.0628947|5.73028|trop
8                 |0.632673|0.0633921|5.55732|trop

L'examen des courbes de speedup révèle une stagnation quasi-totale des performances, quelle que soit la dimension de la matrice ou le nombre de threads utilisés. Les graphiques montrent un speedup qui oscille autour de 1, indiquant que l'exécution parallèle ne parvient pas à réduire le temps de calcul par rapport à la version séquentielle optimisée. Loin de la courbe idéale linéaire, l'ajout de cœurs de calcul n'apporte ici aucun gain significatif.

Ce résultat contre-intuitif s'explique principalement par la saturation de la bande passante mémoire. La version séquentielle que vous avez optimisée précédemment (boucles en j, k, i) est devenue si efficace qu'elle consomme les données aussi vite que la mémoire RAM peut les fournir. Le processeur n'est pas limité par sa capacité de calcul, mais par la vitesse à laquelle les données transitent entre la mémoire principale et les registres.

En conséquence, lorsque plusieurs threads tentent de travailler simultanément, ils se retrouvent en compétition pour accéder au même bus mémoire déjà saturé. Au lieu de calculer en parallèle, les cœurs passent leur temps à attendre leur tour pour lire ou écrire des données, créant un goulot d'étranglement matériel. C'est un cas classique d'application "Memory Bound".

Pour débloquer la situation et obtenir une véritable accélération, il est nécessaire de changer d'approche algorithmique, comme le suggère la suite du sujet. L'utilisation d'une méthode de multiplication par blocs permettrait de mieux exploiter la mémoire cache (beaucoup plus rapide que la RAM) et de réduire la pression sur la bande passante mémoire, autorisant ainsi les threads à travailler sans s'attendre mutuellement.



### Produit par blocs

`make TestProduct.exe && ./TestProduct.exe 1024`

  szBlock         | MFlops  | MFlops(n=512) | MFlops(n=2048)  | MFlops(n=4096)
------------------|---------|----------------|----------------|---------------
origine (=max)    |3472.65|4208.91|3117.91|trop
32                |3481.78|3622.9|3170.57|trop
64                |3505.15|3581.5|4094.87|trop
128               |4043.07|3924.53|3200.84|trop
256               |3793.28|3837.69|3470.55|trop
512               |4145.77|4290.02|3397.96|trop
1024              |3508.98|4209.39|2804.95|trop

Interprétation globale : La méthode par blocs démontre tout son intérêt sur les grandes matrices (n=2048). Alors que la version "origine" (équivalente à prendre tout le bloc d'un coup) voit sa performance chuter à 3117 MFlops à cause de la saturation du cache, le découpage en blocs de taille 64 permet de remonter à 4095 MFlops. Cela représente un gain de performance d'environ 30%.

Rôle de la taille de bloc (szBlock) : Pour n=2048, l'optimum se situe clairement à 64. Cette taille n'est pas due au hasard : trois blocs de 64×64 (matrices A, B et C) en double précision occupent environ 96 Ko, ce qui tient confortablement dans le cache L2 (et partiellement dans le L1) de la plupart des processeurs modernes. Cela permet au processeur de réutiliser les données intensément avant de devoir aller les chercher en RAM.

Comportement sur les petites matrices (n=512) : Pour n=512, la matrice entière (environ 2 Mo) tient probablement déjà entièrement dans le cache L3 (souvent > 6 Mo). Le découpage en blocs n'apporte donc rien de plus ; il ajoute même un léger surcoût de gestion des boucles. C'est pourquoi la meilleure performance est obtenue avec szBlock=512 (c'est-à-dire sans découpage supplémentaire).

Conclusion : Le blocage est une optimisation cruciale pour les problèmes qui dépassent la taille du cache du processeur (ici n=2048). Pour votre machine, une taille de bloc de 64 semble être le "sweet spot" optimal pour maintenir une haute performance indépendamment de la taille totale des matrices.


### Bloc + OMP


  szBlock      | OMP_NUM | MFlops  | MFlops(n=2048) | MFlops(n=512)  | MFlops(n=4096)|
---------------|---------|---------|----------------|----------------|---------------|
1024           |  1      |3279.55|2716.15|3990.39|               |
1024           |  8      |3532.47|2764.87|4192.35|               |
512            |  1      |4210.57|3346.63|4092.24|               |
512            |  8      |4084.93|3378.49|4187.17|               |

Analyse des résultats : Le tableau montre que l'ajout de threads (de 1 à 8) n'améliore pas du tout les performances, le speedup restant bloqué à environ 1. Cela signifie que le calcul parallèle est inefficace avec ces configurations.

Cause du problème : Le souci vient de la taille des blocs trop grande (512 ou 1024) par rapport à la taille de la matrice. Par exemple, pour une matrice de 2048 avec des blocs de 1024, la boucle ne fait que 2 itérations. Si vous avez 8 threads, seulement 2 travaillent et les 6 autres restent inactifs.

Conclusion : Il y a un manque de "grain" à paralléliser. Pour occuper efficacement 8 cœurs, il faudrait soit réduire la taille des blocs (ex: 128) pour créer plus de tâches, soit augmenter drastiquement la taille de la matrice.


### Comparaison avec BLAS, Eigen et numpy

./test_product_matrice_blas.exe 1024 && ./test_product_matrice_blas.exe 512 && ./test_product_matrice_blas.exe 2048

./test_product_matrice_blas.exe 1024 && ./test_product_matrice_blas.exe 512 && ./test_product_matrice_blas.exe 2048
Test passed
Temps CPU produit matrice-matrice blas : 0.588204 secondes
MFlops -> 3650.92
Test passed
Temps CPU produit matrice-matrice blas : 0.0600909 secondes
MFlops -> 4467.16
Test passed
Temps CPU produit matrice-matrice blas : 5.75467 secondes
MFlops -> 2985.38

Dimension (n),Votre Code (Best Manual),BLAS (Standard),Résultat
512,4290 MFlops (sz=512),4467 MFlops,BLAS ≈ Équivalent (+4%)
1024,4145 MFlops (sz=512),3650 MFlops,Votre code gagne (+13%)
2048,4094 MFlops (sz=64),2985 MFlops,Votre code gagne largement (+37%)

Discussion et Analyse :

Le résultat peut sembler surprenant (battre une librairie standard), mais il est logique ici. Nous avons installé libblas-dev, qui fournit généralement l'implémentation de Référence (Netlib). C'est une version générique, "portable", mais non optimisée pour votre processeur spécifique (pas d'instructions AVX2/AVX-512 agressives, pas de multithreading automatique). Notre code C++, compilé avec -O3 -march=native, est mieux optimisé par le compilateur que cette librairie binaire générique.

La gestion de la mémoire (n=2048) : On voit clairement que l'implémentation BLAS standard s'effondre sur les grandes matrices (chute à 2985 MFlops), signe qu'elle gère mal le cache (Memory Bound). Notre version par blocs (szBlock=64) maintient sa performance (~4100 MFlops) car elle force la réutilisation des données en cache L1/L2.

Comparaison avec un "Vrai" BLAS (OpenBLAS / MKL) : Si nous utilisions une version optimisée comme OpenBLAS ou Intel MKL (utilisées par défaut par Numpy ou Matlab), les résultats seraient radicalement différents. Ces librairies atteindraient probablement 50 à 100 GFlops (soit 10 à 20 fois plus vite) en utilisant tous les cœurs et les registres vectoriels.

Conclusion : Vous avez battu la version "basique" de BLAS grâce à une meilleure gestion algorithmique du cache (blocs). Cependant, vous êtes encore loin des performances maximales théoriques de la machine qu'atteindrait une librairie BLAS industrielle (OpenBLAS/MKL).

# Tips

```
	env
	OMP_NUM_THREADS=4 ./produitMatriceMatrice.exe
```

```
    $ for i in $(seq 1 4); do elap=$(OMP_NUM_THREADS=$i ./TestProductOmp.exe|grep "Temps CPU"|cut -d " " -f 7); echo -e "$i\t$elap"; done > timers.out
```