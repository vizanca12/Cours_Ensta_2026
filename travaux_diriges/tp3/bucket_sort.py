from mpi4py import MPI
import numpy as np
import sys

# Configuration initiale MPI
comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()

#Paramètres: nombre d'éléments à trier
N = 20

#Verification: assurer que N est divisible par size
if N % size != 0:
    if rank == 0:
        print("N doit être divisible par le nombre de processus.")
    sys.exit(1) 

#Etape 1: Génération des données aléatoires (seulement par le processus racine)
if rank == 0:
    print("Génération des données aléatoires...")
    data = np.random.rand(N).astype(np.float64)
    print(f"Données générées: {data}")
else:
    data = None

#Etape 2: Distribution des données entre les processus
local_n = N // size #Nombre d'éléments par processus
local_data = np.zeros(local_n, dtype=np.float64)
comm.Scatter(data, local_data, root=0)
local_data.sort() #Tri local des données

#Etape 3: Definition de intervalles (amostrage intelligent)
#Estratégie: chaque processus prend des échantillons de ses données triées

#indices pour pendre des échantillons (ex: debut, milieu, fin)
simple_indices =np.linspace(0, local_n - 1, num=size, dtype=int)
local_samples = local_data[simple_indices]
all_samples = None
if rank == 0:
    all_samples = np.zeros(size * size, dtype=np.float64)

comm.Gather(local_samples, all_samples, root=0)#Rassemblement des échantillons

#Array pour garder les diviseurs (splitters) des buckets
splitters = np.zeros(size - 1, dtype=np.float64)

if rank == 0:
    #Mestre ordonne les échantillons et choisit les diviseurs
    all_samples.sort()
    #Selection (size-1) points de division pour definir (size) intervalles
    #ex: pour size=4, prendre les indices 3, 7, 11
    splitters = all_samples[size:size*size:size].copy() #Prendre les splitters
    print(f"Splitters déterminés: {splitters}")
else: 
    splitters = np.empty(size - 1, dtype=np.float64)

#Transmission des splitters à tous les processus
comm.Bcast(splitters, root=0)

#Etape 4: Distribution des données dans les buckets
#Maintenant chaque processus distribue ses données locales dans les buckets
#Utilisation de np.searchsorted pour trouver les indices des buckets
bucket_indices = np.searchsorted(splitters, local_data)


#Calcul  de combien d'éléments chaque processus envoie à chaque autre processus
send_counts = np.zeros(size, dtype=np.int32)
for dest_proc in bucket_indices:
    send_counts[dest_proc] += 1

#Echange des informations par rapport les comptes: Combien chaque processus recevra
recv_counts = np.zeros(size, dtype=np.int32)
#AlltoAll pour échanger les comptes
comm.Alltoall(send_counts, recv_counts)

#Préparation des buffers pour l'envoi et la réception des données
sort_order = np.argsort(bucket_indices)
send_buffer = local_data[sort_order]

#Calcul des déplacements pour l'envoi et la réception
send_displs = np.insert(np.cumsum(send_counts), 0, 0)[0:-1]
recv_displs = np.insert(np.cumsum(recv_counts), 0, 0)[0:-1]
total_recv = np.sum(recv_counts)
recv_buffer = np.zeros(total_recv, dtype=np.float64)
#Alltoallv pour échanger les données entre les processus
comm.Alltoallv(
    [send_buffer, send_counts, send_displs, MPI.DOUBLE],
    [recv_buffer, recv_counts, recv_displs, MPI.DOUBLE]
)

#Etape 5: Tri local final des données reçues
recv_buffer.sort()
#Collecte des données triées finales au processus racine
final_local_bucket = recv_buffer


#Gather dans le Mestre
#Como os baldes tem tamanhos diferente, precismaos usar Gatherv
#Primeiro o mestre precisa saber quantos elementos cada processo tem
final_counts = None 

final_counts = None
if rank == 0:
    final_counts = np.zeros(size, dtype=np.int32)

#Chaque processus envoie le size de son balde final
local_final_count = np.array([len(final_local_bucket)], dtype=np.int32)
comm.Gather(local_final_count, final_counts, root=0)

#Le mestre prépare les desplacements pour Gatherv
final_data = None
final_displs = None
if rank == 0:
    final_displs = np.insert(np.cumsum(final_counts), 0, 0)[0:-1]
    final_data = np.empty(N, dtype=np.float64)

comm.Gatherv(
    final_local_bucket,
    [final_data, final_counts, final_displs, MPI.DOUBLE] if rank == 0 else None,
    root=0
)

#Etape 6: Affichage des résultats
if rank == 0:
    print("-" * 30)
    print("Ordenance terminée.")
    print(f"Donneés finales (primiers 10): {final_data[:10]}...")
    
    # Verifica se está realmente ordenado
    is_sorted = np.all(final_data[:-1] <= final_data[1:])
    if is_sorted:
        print("Succès")
    else:
        print("ERRO: Les données ne sont pas triées correctement.")
    print("-" * 30)