# Rapport Technique : Optimisation et Parallélisation du Jeu de la Vie (TP4)

## Introduction et Objectifs
Ce travail pratique explore la transition d'une implémentation algorithmique ingénue vers une architecture de haute performance (HPC) utilisant la vectorisation avec NumPy/SciPy et le parallélisme distribué via MPI (Message Passing Interface).

## Évolution des Implémentations

### 1. L'Approche Scalaire (game_of_life.py)
L'implémentation initiale repose sur une logique strictement scalaire, traitant la grille au moyen de boucles imbriquées (for loops). Dans cette version, l'état de chaque cellule est calculé individuellement après vérification manuelle de ses huit voisins. Bien que cette approche soit intuitive et facilite le débogage initial, elle souffre considérablement de l'overhead de l'interpréteur Python. Dans les langages interprétés, l'exécution de millions d'itérations au niveau de l'application est inefficace car elle ne profite ni de la localité des données ni des instructions SIMD (Single Instruction, Multiple Data) du processeur. Par conséquent, cette version sert uniquement de preuve de concept et de base de comparaison pour le coût computationnel.

### 2. Vectorisation et Convolution (game_of_life_vect.py)
Pour surmonter les limitations de la version scalaire, la deuxième implémentation introduit la vectorisation via la bibliothèque NumPy et la fonction convolve2d de SciPy. Le cœur de cette optimisation consiste à traiter la grille non pas comme une collection de points indépendants, mais comme un champ tensoriel. En utilisant un noyau (kernel) de convolution 3x3, où le centre est à zéro et les bordures sont unitaires, nous parvenons à sommer l'état de tous les voisins simultanément pour l'ensemble de la matrice.

L'efficacité est ici doublée : d'une part, les calculs internes sont exécutés par des bibliothèques compilées (C/Fortran), et d'autre part, nous réduisons la complexité algorithmique perçue par Python. La fonction de transition d'état a été optimisée pour utiliser des masques booléens, permettant d'appliquer les règles de survie et de naissance en bloc. L'utilisation du paramètre boundary='wrap' est fondamentale pour simuler un univers toroïdal, où les bords du maillage se rejoignent continuellement.

### 3. Parallélisme Distribué avec MPI (game_of_life_final.py)
Dans cette étape, la grille globale est divisée en sous-domaines, où chaque processus (ou rank) est responsable d'une tranche horizontale de la matrice. Le défi technique ne réside pas seulement dans le calcul local, mais dans la communication aux frontières. L'état d'une cellule dépendant de ses voisins, les cellules situées sur les bords d'un processus doivent connaître les données des processus adjacents.

Pour résoudre cela, j'ai implémenté la technique de Halo Exchange (Échange de Halos). Chaque processus maintient des lignes supplémentaires, appelées "ghost cells" (cellules fantômes). Avant chaque itération, les processus effectuent des échanges de messages asynchrones : le processus $n$ envoie sa bordure inférieure au processus $n+1$ et sa bordure supérieure au processus $n-1$. L'utilisation de communications non-bloquantes (Isend et Irecv) est un choix de conception critique pour permettre le chevauchement du calcul et de la communication, minimisant ainsi le temps d'attente du processeur.

### 4. Intégration et Visualisation Parallèle (game_of_life_vect_final.py)
Dans cette architecture, le Rank 0 assume le rôle de coordonnateur pour l'interface visuelle. Tandis que tous les processus calculent leurs tranches en parallèle, le coordonnateur effectue une opération Gather (rassemblement) pour consolider la grille complète et l'afficher à l'écran.

Il est important de noter que la visualisation graphique est souvent le goulot d'étranglement des systèmes parallèles. Pour atténuer cet effet, la fonction de dessin a été optimisée pour n'itérer que sur les cellules vivantes à l'aide de la méthode np.where, ce qui réduit considérablement la charge graphique sur des grilles éparses.

---


## Guide d'Exécution

### Prérequis
Assurez-vous d'avoir installé les bibliothèques nécessaires dans votre environnement Python :

```bash
pip install numpy scipy pygame mpi4py
```

## Commandes d'Exécution

1. Versions Séquentielles (Tests logiques) :


```Bash

python game_of_life.py glider
python game_of_life_vect.py pulsar
```

2. Versions Parallèles (Haute Performance) :


```Bash

# Version focalisée sur l'analyse de performance (sans interface)
mpirun -n 4 python game_of_life_final.py glider_gun

# Version complète avec visualisation graphique
mpirun -n 4 python game_of_life_vect_final.py space_ship
```

