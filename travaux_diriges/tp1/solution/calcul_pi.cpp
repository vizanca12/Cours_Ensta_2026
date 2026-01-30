# include <chrono>
# include <random>
# include <cstdlib>
# include <sstream>
# include <string>
# include <fstream>
# include <iostream>
# include <iomanip>
# include <mpi.h>

// Attention , ne marche qu'en C++ 11 ou supérieur :
double approximate_pi( unsigned long nbSamples ) 
{
	typedef std::chrono::high_resolution_clock myclock;
    myclock::time_point beginning = myclock::now();
    myclock::duration d = beginning.time_since_epoch();
    unsigned seed = d.count();
    std::default_random_engine generator(seed);
    std::uniform_real_distribution <double> distribution ( -1.0 ,1.0);
    unsigned long nbDarts = 0;
    // Throw nbSamples darts in the unit square [-1 :1] x [-1 :1]
    for ( unsigned sample = 0 ; sample < nbSamples ; ++ sample ) {
        double x = distribution(generator);
        double y = distribution(generator);
        // Test if the dart is in the unit disk
        if ( x*x+y*y<=1 ) nbDarts ++;
    }
    // Number of nbDarts throwed in the unit disk
    double ratio = double(nbDarts);
    return 4*ratio;
}

int main( int nargs, char* argv[] )
{
	// On initialise le contexte MPI qui va s'occuper :
	//    1. Créer un communicateur global, COMM_WORLD qui permet de gérer
	//       et assurer la cohésion de l'ensemble des processus créés par MPI;
	//    2. d'attribuer à chaque processus un identifiant ( entier ) unique pour
	//       le communicateur COMM_WORLD
	//    3. etc...
	MPI_Init( &nargs, &argv );
	// Pour des raisons de portabilité qui débordent largement du cadre
	// de ce cours, on préfère toujours cloner le communicateur global
	// MPI_COMM_WORLD qui gère l'ensemble des processus lancés par MPI.
	MPI_Comm globComm;
	MPI_Comm_dup(MPI_COMM_WORLD, &globComm);
	// On interroge le communicateur global pour connaître le nombre de processus
	// qui ont été lancés par l'utilisateur :
	int nbp;
	MPI_Comm_size(globComm, &nbp);
	// On interroge le communicateur global pour connaître l'identifiant qui
	// m'a été attribué ( en tant que processus ). Cet identifiant est compris
	// entre 0 et nbp-1 ( nbp étant le nombre de processus qui ont été lancés par
	// l'utilisateur )
	int rank;
	MPI_Comm_rank(globComm, &rank);
	// Création d'un fichier pour ma propre sortie en écriture :
	std::stringstream fileName;
	fileName << "Output" << std::setfill('0') << std::setw(5) << rank << ".txt";
	std::ofstream output( fileName.str().c_str() );

	unsigned long nb_samples = 100'000'000;
	unsigned long nb_samples_loc = nb_samples/static_cast<unsigned long>(nbp) + 
	      (static_cast<unsigned long>(rank) < nb_samples%static_cast<unsigned long>(nbp) ? 1UL : 0UL);
	output << "Nombre d'echantillpons a produire : " << nb_samples_loc << std::endl;


	MPI_Status status;
    std::chrono::time_point<std::chrono::system_clock> beginning = std::chrono::system_clock::now();
	std::chrono::time_point<std::chrono::system_clock> ending;
	double val_pi = approximate_pi(nb_samples_loc);
	if (rank==0)
	{
		for (int p = 1; p < nbp; ++p)
		{
			double val;
			MPI_Recv(&val,1,MPI_DOUBLE,p,101,globComm,&status);
			val_pi += val;
		}
		val_pi /= nb_samples;
		ending = std::chrono::system_clock::now();
		output << "approximation de pi : " << val_pi << std::endl;
		std::chrono::duration < double > elapsed_seconds = ending - beginning;
		output << "Temps de calcul : " << elapsed_seconds.count() << "s" << std::endl;
	}
	else 
	{
		MPI_Send(&val_pi,1, MPI_DOUBLE,0,101,globComm);
		ending = std::chrono::system_clock::now();
		std::chrono::duration < double > elapsed_seconds = ending - beginning;
		output << "Temps de calcul : " << elapsed_seconds.count() << "s" << std::endl;
	}
	output.close();
	// A la fin du programme, on doit synchroniser une dernière fois tous les processus
	// afin qu'aucun processus ne se termine pendant que d'autres processus continue à
	// tourner. Si on oublie cet instruction, on aura une plantage assuré des processus
	// qui ne seront pas encore terminés.
	MPI_Finalize();
	return EXIT_SUCCESS;
}

