#include <vector>
#include <iostream>
#include <string>
#include <chrono>
#include <random>
#include <omp.h>
#include "fractal_land.hpp"
#include "ant.hpp"
#include "pheronome.hpp"
# include "renderer.hpp"
# include "window.hpp"
# include "rand_generator.hpp"

namespace {
struct Options {
    std::size_t seed = 2026;
    int nb_ants = 5000;
    std::size_t steps = 0;   // 0 => boucle infinie (mode interactif)
    bool no_gui = false;
    bool vectorized = false; // SoA (benchmark)
};

struct Timings {
    double ants_s = 0.0;
    double evap_s = 0.0;
    double update_s = 0.0;
    double render_s = 0.0;
    std::size_t iters = 0;
};

Options parse_args(int nargs, char* argv[])
{
    Options opt;
    for (int i = 1; i < nargs; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            std::cout
                << "Usage: " << argv[0] << " [--steps N] [--no-gui] [--ants M] [--seed S]\n"
                << "  --steps N   Nombre d'iterations (0 = interactif, infini)\n"
                << "  --no-gui    Desactive SDL/render (benchmark)\n"
                << "  --vectorized Utilise une representation SoA (requiert --no-gui)\n"
                << "  --ants M    Nombre de fourmis\n"
                << "  --seed S    Graine RNG\n";
            std::exit(0);
        } else if (arg == "--steps" && i + 1 < nargs) {
            opt.steps = std::stoull(argv[++i]);
        } else if (arg == "--no-gui") {
            opt.no_gui = true;
        } else if (arg == "--vectorized") {
            opt.vectorized = true;
        } else if (arg == "--ants" && i + 1 < nargs) {
            opt.nb_ants = std::stoi(argv[++i]);
        } else if (arg == "--seed" && i + 1 < nargs) {
            opt.seed = std::stoull(argv[++i]);
        } else {
            std::cerr << "Unknown argument: " << arg << " (use --help)\n";
            std::exit(2);
        }
    }
    return opt;
}

void advance_time_timed( const fractal_land& land, pheronome& phen,
                         const position_t& pos_nest, const position_t& pos_food,
                         std::vector<ant>& ants, std::size_t& cpteur,
                         Timings& timings )
{
    using clock = std::chrono::steady_clock;
    auto t0 = clock::now();

    std::vector<std::vector<position_t>> marks_per_thread(static_cast<std::size_t>(omp_get_max_threads()));
    std::vector<std::size_t> food_per_thread(static_cast<std::size_t>(omp_get_max_threads()), 0);

#pragma omp parallel
    {
        const int tid = omp_get_thread_num();
        auto& local_marks = marks_per_thread[static_cast<std::size_t>(tid)];
        std::size_t local_food = 0;

#pragma omp for schedule(static)
        for ( std::size_t i = 0; i < ants.size(); ++i )
            ants[i].advance(phen, land, pos_food, pos_nest, local_food, &local_marks);

        food_per_thread[static_cast<std::size_t>(tid)] = local_food;
    }

    for (std::size_t food : food_per_thread)
        cpteur += food;

    for (const auto& marks : marks_per_thread)
        for (const auto& pos : marks)
            phen.mark_pheronome(pos);

    auto t1 = clock::now();
    phen.do_evaporation();
    auto t2 = clock::now();
    phen.update();
    auto t3 = clock::now();

    timings.ants_s += std::chrono::duration<double>(t1 - t0).count();
    timings.evap_s += std::chrono::duration<double>(t2 - t1).count();
    timings.update_s += std::chrono::duration<double>(t3 - t2).count();
    timings.iters += 1;
}

struct AntSoA {
    std::vector<int> x;
    std::vector<int> y;
    std::vector<unsigned char> loaded;
    std::vector<std::size_t> seed;

    std::size_t size() const { return x.size(); }
};

void advance_time_timed_soa( const fractal_land& land, pheronome& phen,
                             const position_t& pos_nest, const position_t& pos_food,
                             AntSoA& ants, std::size_t& cpteur,
                             double eps, Timings& timings )
{
    constexpr double k_min_step_cost = 1e-3;
    constexpr int k_max_substeps = 4096;
    constexpr int k_max_random_tries = 64;
    using clock = std::chrono::steady_clock;
    auto t0 = clock::now();
    auto& ants_x = ants.x;
    auto& ants_y = ants.y;
    auto& ants_loaded = ants.loaded;
    auto& ants_seed = ants.seed;

    std::vector<std::vector<position_t>> marks_per_thread(static_cast<std::size_t>(omp_get_max_threads()));
    std::size_t food_delta = 0;

#pragma omp parallel reduction(+ : food_delta)
    {
        const int tid = omp_get_thread_num();
        auto& local_marks = marks_per_thread[static_cast<std::size_t>(tid)];

#pragma omp for schedule(static)
        for ( std::size_t idx = 0; idx < ants.size(); ++idx ) {
            int ant_x = ants_x[idx];
            int ant_y = ants_y[idx];
            unsigned char ant_loaded = ants_loaded[idx];
            std::size_t ant_seed = ants_seed[idx];
            double consumed_time = 0.0;
            int substeps = 0;

            while ( ( consumed_time < 1.0 ) && ( substeps < k_max_substeps ) ) {
                const int ind_pher = ( ant_loaded ? 1 : 0 );
                const double choix = rand_double( 0., 1., ant_seed );
                const int old_x = ant_x;
                const int old_y = ant_y;
                int new_x = ant_x;
                int new_y = ant_y;

                const double max_phen = std::max({
                    phen( new_x - 1, new_y )[ind_pher],
                    phen( new_x + 1, new_y )[ind_pher],
                    phen( new_x, new_y - 1 )[ind_pher],
                    phen( new_x, new_y + 1 )[ind_pher],
                });

                if ( ( choix > eps ) || ( max_phen <= 0. ) ) {
                    position_t trial{old_x, old_y};
                    bool found = false;
                    for ( int tries = 0; tries < k_max_random_tries; ++tries ) {
                        trial.x = old_x;
                        trial.y = old_y;
                        const int d = rand_int32( 1, 4, ant_seed );
                        if ( d == 1 ) trial.x -= 1;
                        if ( d == 2 ) trial.y -= 1;
                        if ( d == 3 ) trial.x += 1;
                        if ( d == 4 ) trial.y += 1;
                        if ( phen[trial][ind_pher] != -1 ) {
                            found = true;
                            break;
                        }
                    }
                    if ( !found ) {
                        trial.x = old_x;
                        trial.y = old_y;
                    }
                    new_x = trial.x;
                    new_y = trial.y;
                } else {
                    if ( phen( new_x - 1, new_y )[ind_pher] == max_phen )
                        new_x -= 1;
                    else if ( phen( new_x + 1, new_y )[ind_pher] == max_phen )
                        new_x += 1;
                    else if ( phen( new_x, new_y - 1 )[ind_pher] == max_phen )
                        new_y -= 1;
                    else
                        new_y += 1;
                }

                consumed_time += std::max(
                    land( static_cast<unsigned long>(new_x), static_cast<unsigned long>(new_y) ),
                    k_min_step_cost );
                ++substeps;
                position_t new_pos{new_x, new_y};
                local_marks.push_back( new_pos );
                ant_x = new_x;
                ant_y = new_y;

                if ( new_pos == pos_nest ) {
                    if ( ant_loaded )
                        food_delta += 1;
                    ant_loaded = 0;
                }
                if ( new_pos == pos_food ) {
                    ant_loaded = 1;
                }
            }

            ants_x[idx] = ant_x;
            ants_y[idx] = ant_y;
            ants_loaded[idx] = ant_loaded;
            ants_seed[idx] = ant_seed;
        }
    }

    cpteur += food_delta;

    for (const auto& marks : marks_per_thread)
        for (const auto& pos : marks)
            phen.mark_pheronome(pos);

    auto t1 = clock::now();
    phen.do_evaporation();
    auto t2 = clock::now();
    phen.update();
    auto t3 = clock::now();

    timings.ants_s += std::chrono::duration<double>(t1 - t0).count();
    timings.evap_s += std::chrono::duration<double>(t2 - t1).count();
    timings.update_s += std::chrono::duration<double>(t3 - t2).count();
    timings.iters += 1;
}
} // namespace

int main(int nargs, char* argv[])
{
    Options opt = parse_args(nargs, argv);
    if (opt.vectorized && !opt.no_gui) {
        std::cerr << "--vectorized requires --no-gui (no renderer integration yet).\n";
        return 2;
    }
    if (!opt.no_gui) {
        SDL_Init( SDL_INIT_VIDEO );
    }
    std::size_t seed = opt.seed; // Graine pour la génération aléatoire ( reproductible )
    const std::size_t nb_ants = static_cast<std::size_t>(opt.nb_ants); // Nombre de fourmis
    const double eps = 0.8;  // Coefficient d'exploration
    const double alpha=0.7; // Coefficient de chaos
    //const double beta=0.9999; // Coefficient d'évaporation
    const double beta=0.999; // Coefficient d'évaporation
    // Location du nid
    position_t pos_nest{256,256};
    // Location de la nourriture
    position_t pos_food{500,500};
    //const int i_food = 500, j_food = 500;    
    // Génération du territoire 512 x 512 ( 2*(2^8) par direction )
    fractal_land land(8,2,1.,1024);
    double max_val = 0.0;
    double min_val = 0.0;
    for ( fractal_land::dim_t i = 0; i < land.dimensions(); ++i )
        for ( fractal_land::dim_t j = 0; j < land.dimensions(); ++j ) {
            max_val = std::max(max_val, land(i,j));
            min_val = std::min(min_val, land(i,j));
        }
    double delta = max_val - min_val;
    /* On redimensionne les valeurs de fractal_land de sorte que les valeurs
    soient comprises entre zéro et un */
    for ( fractal_land::dim_t i = 0; i < land.dimensions(); ++i )
        for ( fractal_land::dim_t j = 0; j < land.dimensions(); ++j )  {
            land(i,j) = (land(i,j)-min_val)/delta;
        }
    // Définition du coefficient d'exploration de toutes les fourmis.
    ant::set_exploration_coef(eps);
    // On va créer des fourmis un peu partout sur la carte :
    std::vector<ant> ants;
    AntSoA ants_soa;
    auto gen_ant_pos = [&land, &seed] () { return rand_int32(0, static_cast<std::int32_t>(land.dimensions()-1), seed); };
    if (!opt.vectorized) {
        ants.reserve(nb_ants);
        for ( std::size_t i = 0; i < nb_ants; ++i )
            ants.emplace_back(position_t{gen_ant_pos(), gen_ant_pos()}, seed);
    } else {
        ants_soa.x.reserve(nb_ants);
        ants_soa.y.reserve(nb_ants);
        ants_soa.loaded.reserve(nb_ants);
        ants_soa.seed.reserve(nb_ants);
        for ( std::size_t i = 0; i < nb_ants; ++i ) {
            ants_soa.x.push_back(gen_ant_pos());
            ants_soa.y.push_back(gen_ant_pos());
            ants_soa.loaded.push_back(0);
            ants_soa.seed.push_back(seed);
        }
    }
    // On crée toutes les fourmis dans la fourmilière.
    pheronome phen(land.dimensions(), pos_food, pos_nest, alpha, beta);

    Window* win = nullptr;
    Renderer* renderer = nullptr;
    if (!opt.no_gui) {
        win = new Window("Ant Simulation", 2*land.dimensions()+10, land.dimensions()+266);
        renderer = new Renderer( land, phen, pos_nest, pos_food, ants );
    }
    // Compteur de la quantité de nourriture apportée au nid par les fourmis
    size_t food_quantity = 0;
    SDL_Event event;
    bool cont_loop = true;
    bool not_food_in_nest = true;
    std::size_t it = 0;
    Timings timings;

    const auto render_step = [&]() {
        using clock = std::chrono::steady_clock;
        if (opt.no_gui) return;
        auto t0 = clock::now();
        renderer->display( *win, food_quantity );
        win->blit();
        auto t1 = clock::now();
        timings.render_s += std::chrono::duration<double>(t1 - t0).count();
    };

    if (opt.steps > 0) {
        for (it = 1; it <= opt.steps; ++it) {
            if (!opt.no_gui) {
                while (SDL_PollEvent(&event)) {
                    if (event.type == SDL_QUIT) {
                        cont_loop = false;
                    }
                }
                if (!cont_loop) break;
            }
            if (!opt.vectorized)
                advance_time_timed( land, phen, pos_nest, pos_food, ants, food_quantity, timings );
            else
                advance_time_timed_soa( land, phen, pos_nest, pos_food, ants_soa, food_quantity, eps, timings );
            render_step();
            if ( not_food_in_nest && food_quantity > 0 ) {
                std::cout << "La première nourriture est arrivée au nid a l'iteration " << it << std::endl;
                not_food_in_nest = false;
            }
        }
    } else {
        while (cont_loop) {
            ++it;
            while (!opt.no_gui && SDL_PollEvent(&event)) {
                if (event.type == SDL_QUIT)
                    cont_loop = false;
            }
            if (!cont_loop) break;
            if (!opt.vectorized)
                advance_time_timed( land, phen, pos_nest, pos_food, ants, food_quantity, timings );
            else
                advance_time_timed_soa( land, phen, pos_nest, pos_food, ants_soa, food_quantity, eps, timings );
            render_step();
            if ( not_food_in_nest && food_quantity > 0 ) {
                std::cout << "La première nourriture est arrivée au nid a l'iteration " << it << std::endl;
                not_food_in_nest = false;
            }
        }
    }

    if (timings.iters > 0) {
        const double iters = static_cast<double>(timings.iters);
        std::cout << "\n==== Timings (total) ====\n";
        const std::size_t ants_count = opt.vectorized ? ants_soa.size() : ants.size();
        std::cout << "iters: " << timings.iters << " ants: " << ants_count;
        if (opt.vectorized) std::cout << " (SoA)";
        std::cout << "\n";
        std::cout << "ants.advance: " << timings.ants_s << " s\n";
        std::cout << "pheromone.evap: " << timings.evap_s << " s\n";
        std::cout << "pheromone.update: " << timings.update_s << " s\n";
        if (!opt.no_gui) std::cout << "render: " << timings.render_s << " s\n";
        std::cout << "\n==== Timings (avg/iter) ====\n";
        std::cout << "ants.advance: " << (timings.ants_s / iters) << " s\n";
        std::cout << "pheromone.evap: " << (timings.evap_s / iters) << " s\n";
        std::cout << "pheromone.update: " << (timings.update_s / iters) << " s\n";
        if (!opt.no_gui) std::cout << "render: " << (timings.render_s / iters) << " s\n";
    }

    delete renderer;
    delete win;
    if (!opt.no_gui) {
        SDL_Quit();
    }
    return 0;
}