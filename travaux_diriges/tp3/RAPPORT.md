# Tri par Casier Parallèle (Bucket Sort) avec MPI

Ce projet implémente l'algorithme de **Bucket Sort (Tri par Casier)** de manière parallèle en utilisant Python et la bibliothèque `mpi4py`.

L'objectif est de trier un vecteur de nombres aléatoires en distribuant la charge de travail sur plusieurs processus. L'algorithme utilise une stratégie de choix de pivots dynamiques pour s'assurer que chaque "casier" (bucket) reçoive une quantité équilibrée de données.

## 📋 Fonctionnement de l'Algorithme

Le code suit les étapes classiques du Bucket Sort adapté aux systèmes distribués :

1.  **Génération :** Le processus racine génère $N$ nombres aléatoires.
2.  **Distribution (Scatter) :** Les données sont divisées équitablement entre les processus pour une première analyse.
3.  **Calcul des Pivots (Splitters) :**
    * Chaque processus trie ses données locales et propose des échantillons.
    * Le processus racine collecte ces échantillons pour définir des **pivots** (splitters) qui diviseront globalement les données en intervalles (casiers) équilibrés.
4.  **Distribution dans les Casiers (Alltoallv) :** Chaque processus envoie ses données vers le processus responsable de l'intervalle correspondant (le "casier").
5.  **Tri Local :** Chaque processus trie les données reçues dans son casier.
6.  **Assemblage (Gather) :** Le vecteur final trié est reconstitué sur le processus racine.

## 🛠 Prérequis

* **Langage :** Python 3.x
* **Bibliothèques :** `mpi4py`, `numpy`
* **Système MPI :** OpenMPI, MPICH ou MS-MPI (Windows)

Installation des dépendances :
```bash
pip install mpi4py numpy

``` 

# 📊 Résultats d'Exécution

## Test 1 : Exécution avec 5 Processus

```
Génération des données aléatoires...
Données générées: [0.48888249 0.12177848 0.33647475 0.16400492 0.9999071  0.29098018
 0.37876028 0.73678803 0.80500308 0.29537192 0.01258442 0.09184158
 0.2647151  0.58629522 0.63407125 0.64023887 0.17104206 0.97542785
 0.72488841 0.83074544]

Splitters déterminés: [0.16400492 0.29098018 0.48888249 0.73678803]
------------------------------
Ordenance terminée.
Donneés finales (primiers 10): [0.01258442 0.09184158 0.12177848 0.16400492 0.17104206 0.2647151
 0.29098018 0.29537192 0.33647475 0.37876028]...
Succès
------------------------------
```

## Test 2 : Exécution avec 2 Processus

```
Génération des données aléatoires...
Données générées: [0.67207149 0.60661762 0.40199651 0.62849138 0.11527718 0.33740893
 0.2548419  0.0426579  0.62769022 0.49941993 0.92971957 0.3361567
 0.50235298 0.2470816  0.45408729 0.67938257 0.66406335 0.72065587
 0.69782661 0.43471985]

Splitters déterminés: [0.67207149]
------------------------------
Ordenance terminée.
Donneés finales (primiers 10): [0.0426579  0.11527718 0.2470816  0.2548419  0.3361567  0.33740893
 0.40199651 0.43471985 0.45408729 0.49941993]...
Succès
-----------------------------
```

