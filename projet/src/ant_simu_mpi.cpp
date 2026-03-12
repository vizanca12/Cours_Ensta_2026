#include <mpi.h>

#include <omp.h>

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "ant.hpp"
#include "basic_types.hpp"
#include "fractal_land.hpp"
#include "pheronome.hpp"
#include "rand_generator.hpp"

namespace {
struct Options {
    std::size_t seed = 2026;
    std::size_t steps = 200;
    std::size_t nb_ants_total = 5000;
    double eps = 0.8;
    double alpha = 0.7;
    double beta = 0.999;
    int omp_threads = 1;
};

struct Timings {
    double ants_s = 0.0;
    double evap_s = 0.0;
    double update_s = 0.0;
    double allreduce_s = 0.0;
    double wall_s = 0.0;
    std::size_t iters = 0;
};

Options parse_args(int nargs, char* argv[])
{
    Options opt;
    for (int i = 1; i < nargs; ++i) {
        std::string arg = argv[i];
        if (arg == "--help" || arg == "-h") {
            std::cout
                << "Usage: " << argv[0]
                << " [--steps N] [--ants M] [--seed S] [--eps E] [--alpha A] [--beta B] [--omp-threads T]\n"
                << "  --steps N   Nombre d'iterations (default 200)\n"
                << "  --ants M    Nombre total de fourmis (toutes ranks confondues)\n"
                << "  --seed S    Graine RNG\n"
                << "  --eps E     Taux d'exploration\n"
                << "  --alpha A   Parametre de bruit pheromone\n"
                << "  --beta B    Evaporation pheromone\n"
                << "  --omp-threads T  Threads OpenMP par rank (default 1)\n";
            std::exit(0);
        } else if (arg == "--steps" && i + 1 < nargs) {
            opt.steps = std::stoull(argv[++i]);
        } else if (arg == "--ants" && i + 1 < nargs) {
            opt.nb_ants_total = std::stoull(argv[++i]);
        } else if (arg == "--seed" && i + 1 < nargs) {
            opt.seed = std::stoull(argv[++i]);
        } else if (arg == "--eps" && i + 1 < nargs) {
            opt.eps = std::stod(argv[++i]);
        } else if (arg == "--alpha" && i + 1 < nargs) {
            opt.alpha = std::stod(argv[++i]);
        } else if (arg == "--beta" && i + 1 < nargs) {
            opt.beta = std::stod(argv[++i]);
        } else if (arg == "--omp-threads" && i + 1 < nargs) {
            opt.omp_threads = std::stoi(argv[++i]);
        } else {
            std::cerr << "Unknown argument: " << arg << " (use --help)\n";
            std::exit(2);
        }
    }
    return opt;
}

struct AntSoA {
    std::vector<int> x;
    std::vector<int> y;
    std::vector<unsigned char> loaded;
    std::vector<std::size_t> seed;

    std::size_t size() const { return x.size(); }
};

static inline void normalize_land(fractal_land& land)
{
    double max_val = 0.0;
    double min_val = 0.0;
    for (fractal_land::dim_t i = 0; i < land.dimensions(); ++i)
        for (fractal_land::dim_t j = 0; j < land.dimensions(); ++j) {
            max_val = std::max(max_val, land(i, j));
            min_val = std::min(min_val, land(i, j));
        }
    const double delta = max_val - min_val;
    for (fractal_land::dim_t i = 0; i < land.dimensions(); ++i)
        for (fractal_land::dim_t j = 0; j < land.dimensions(); ++j) {
            land(i, j) = (land(i, j) - min_val) / delta;
        }
}

static inline void compute_local_range(std::size_t n_total, int rank, int n_ranks,
                                      std::size_t& begin, std::size_t& end)
{
    const std::size_t base = n_total / static_cast<std::size_t>(n_ranks);
    const std::size_t rem = n_total % static_cast<std::size_t>(n_ranks);
    const std::size_t r = static_cast<std::size_t>(rank);
    begin = r * base + std::min<std::size_t>(r, rem);
    end = begin + base + (r < rem ? 1 : 0);
}

void advance_local_ants(const fractal_land& land, pheronome& phen,
                        const position_t& pos_nest, const position_t& pos_food,
                        AntSoA& ants, std::size_t& local_food_counter,
                        double eps)
{
    constexpr double k_min_step_cost = 1e-3;
    constexpr int k_max_substeps = 4096;
    constexpr int k_max_random_tries = 64;
    for (std::size_t idx = 0; idx < ants.size(); ++idx) {
        double consumed_time = 0.0;
        int substeps = 0;
        while ((consumed_time < 1.0) && (substeps < k_max_substeps)) {
            const int ind_pher = (ants.loaded[idx] ? 1 : 0);
            const double choix = rand_double(0., 1., ants.seed[idx]);

            const int old_x = ants.x[idx];
            const int old_y = ants.y[idx];
            int new_x = old_x;
            int new_y = old_y;

            const double max_phen = std::max({
                phen(new_x - 1, new_y)[ind_pher],
                phen(new_x + 1, new_y)[ind_pher],
                phen(new_x, new_y - 1)[ind_pher],
                phen(new_x, new_y + 1)[ind_pher],
            });

            if ((choix > eps) || (max_phen <= 0.)) {
                position_t trial{old_x, old_y};
                bool found = false;
                for (int tries = 0; tries < k_max_random_tries; ++tries) {
                    trial.x = old_x;
                    trial.y = old_y;
                    const int d = rand_int32(1, 4, ants.seed[idx]);
                    if (d == 1) trial.x -= 1;
                    if (d == 2) trial.y -= 1;
                    if (d == 3) trial.x += 1;
                    if (d == 4) trial.y += 1;
                    if (phen[trial][ind_pher] != -1) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    trial.x = old_x;
                    trial.y = old_y;
                }
                new_x = trial.x;
                new_y = trial.y;
            } else {
                if (phen(new_x - 1, new_y)[ind_pher] == max_phen)
                    new_x -= 1;
                else if (phen(new_x + 1, new_y)[ind_pher] == max_phen)
                    new_x += 1;
                else if (phen(new_x, new_y - 1)[ind_pher] == max_phen)
                    new_y -= 1;
                else
                    new_y += 1;
            }

            consumed_time += std::max(
                land(static_cast<unsigned long>(new_x), static_cast<unsigned long>(new_y)),
                k_min_step_cost);
            ++substeps;
            position_t new_pos{new_x, new_y};

            phen.mark_pheronome(new_pos);
            ants.x[idx] = new_x;
            ants.y[idx] = new_y;

            if (new_pos == pos_nest) {
                if (ants.loaded[idx])
                    local_food_counter += 1;
                ants.loaded[idx] = 0;
            }
            if (new_pos == pos_food) {
                ants.loaded[idx] = 1;
            }
        }
    }
}

} // namespace

int main(int nargs, char* argv[])
{
    MPI_Init(&nargs, &argv);

    int rank = 0;
    int n_ranks = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &n_ranks);

    Options opt = parse_args(nargs, argv);

    // Avoid oversubscription by default; allow hybrid MPI+OpenMP via --omp-threads.
    if (opt.omp_threads < 1) opt.omp_threads = 1;
    omp_set_dynamic(0);
    omp_set_num_threads(opt.omp_threads);

    // Environment replicated on all ranks
    position_t pos_nest{256, 256};
    position_t pos_food{500, 500};
    fractal_land land(8, 2, 1., 1024);
    normalize_land(land);

    pheronome phen(land.dimensions(), pos_food, pos_nest, opt.alpha, opt.beta);

    // Distribute ants by contiguous ranges over global indices
    std::size_t begin = 0, end = 0;
    compute_local_range(opt.nb_ants_total, rank, n_ranks, begin, end);
    const std::size_t local_n = end - begin;

    AntSoA ants;
    ants.x.reserve(local_n);
    ants.y.reserve(local_n);
    ants.loaded.reserve(local_n);
    ants.seed.reserve(local_n);

    // Deterministic per-ant initialization (no scatter needed)
    for (std::size_t g = begin; g < end; ++g) {
        std::size_t s = opt.seed + g * 1000003ULL;
        const int x = rand_int32(0, static_cast<std::int32_t>(land.dimensions() - 1), s);
        const int y = rand_int32(0, static_cast<std::int32_t>(land.dimensions() - 1), s);
        ants.x.push_back(x);
        ants.y.push_back(y);
        ants.loaded.push_back(0);
        ants.seed.push_back(s);
    }

    Timings timings;
    std::size_t local_food = 0;

    using clock = std::chrono::steady_clock;
    std::vector<double> reduced;
    reduced.resize(phen.raw_map_doubles_count());

    for (std::size_t it = 0; it < opt.steps; ++it) {
        const double wall0 = MPI_Wtime();
        auto t0 = clock::now();
        advance_local_ants(land, phen, pos_nest, pos_food, ants, local_food, opt.eps);
        auto t1 = clock::now();
        phen.do_evaporation();
        auto t2 = clock::now();
        phen.update_no_sync();
        auto t3 = clock::now();

        // Merge pheromones across ranks: take maximum value for each cell/field
        auto t4 = clock::now();
        MPI_Allreduce(phen.raw_map_doubles(), reduced.data(),
                      static_cast<int>(phen.raw_map_doubles_count()),
                      MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);
        phen.set_map_from_raw_doubles(reduced.data());
        phen.sync_buffer_from_map();
        auto t5 = clock::now();
        const double wall1 = MPI_Wtime();

        timings.ants_s += std::chrono::duration<double>(t1 - t0).count();
        timings.evap_s += std::chrono::duration<double>(t2 - t1).count();
        timings.update_s += std::chrono::duration<double>(t3 - t2).count();
        timings.allreduce_s += std::chrono::duration<double>(t5 - t4).count();
        timings.wall_s += (wall1 - wall0);
        timings.iters += 1;
    }

    // Reduce counters and timings to rank 0
    std::size_t global_food = 0;
    MPI_Reduce(&local_food, &global_food, 1, MPI_UNSIGNED_LONG, MPI_SUM, 0, MPI_COMM_WORLD);

    Timings sum_t;
    MPI_Reduce(&timings.ants_s, &sum_t.ants_s, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&timings.evap_s, &sum_t.evap_s, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&timings.update_s, &sum_t.update_s, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&timings.allreduce_s, &sum_t.allreduce_s, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);

    double wall_max = 0.0;
    MPI_Reduce(&timings.wall_s, &wall_max, 1, MPI_DOUBLE, MPI_MAX, 0, MPI_COMM_WORLD);

    if (rank == 0) {
        const double iters = static_cast<double>(timings.iters);
        std::cout << "==== MPI Ant Simulation (Approach 1) ====\n";
        std::cout << "ranks: " << n_ranks << " ants_total: " << opt.nb_ants_total
                  << " steps: " << opt.steps << "\n";
        std::cout << "food_total: " << global_food << "\n\n";

        std::cout << "==== Wall-time (max rank) ====\n";
        std::cout << "total: " << wall_max << " s\n";
        std::cout << "per-iter: " << (wall_max / iters) << " s\n\n";

        // Show average per-rank times (sum / nranks)
        std::cout << "==== Timings (avg rank, total) ====\n";
        std::cout << "ants.advance: " << (sum_t.ants_s / n_ranks) << " s\n";
        std::cout << "pheromone.evap: " << (sum_t.evap_s / n_ranks) << " s\n";
        std::cout << "pheromone.update: " << (sum_t.update_s / n_ranks) << " s\n";
        std::cout << "MPI_Allreduce(max): " << (sum_t.allreduce_s / n_ranks) << " s\n\n";

        std::cout << "==== Timings (avg rank, per-iter) ====\n";
        std::cout << "ants.advance: " << (sum_t.ants_s / n_ranks / iters) << " s\n";
        std::cout << "pheromone.evap: " << (sum_t.evap_s / n_ranks / iters) << " s\n";
        std::cout << "pheromone.update: " << (sum_t.update_s / n_ranks / iters) << " s\n";
        std::cout << "MPI_Allreduce(max): " << (sum_t.allreduce_s / n_ranks / iters) << " s\n";
    }

    MPI_Finalize();
    return 0;
}
