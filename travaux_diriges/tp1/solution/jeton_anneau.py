from mpi4py import MPI

globCom = MPI.COMM_WORLD.Dup()
rank = globCom.rank
nbp  = globCom.size

jeton = None
if rank==0: 
    jeton = 1
    globCom.send(jeton,dest=1,tag=101)
    jeton = globCom.recv(source=nbp-1,tag=101)
    print(f"jeton reçu : {jeton}")
else:
    jeton = globCom.recv(source=rank-1,tag=101)
    jeton += 1
    globCom.send(jeton,dest=(rank+1)%nbp, tag=101)
