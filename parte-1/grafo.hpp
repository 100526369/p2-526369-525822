
#ifndef GRAFO_HPP
#define GRAFO_HPP

#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>
#include <stdexcept>

#include "estado.hpp"

namespace airport_search {

class AirportGraph {
public:

    // Adds an airport to the graph
    void add_airport(const AirportState& airport) {

        airports_.insert_or_assign(
            std::string(airport.get_IATA()),
            airport
        );
    }

    // Adds a directed connection between two airports
    void add_neighbour(
        std::string_view from,
        std::string_view to
    ) {

        const std::string origin(from);
        const std::string destination(to);

        if (airports_.find(origin) == airports_.end() ||
            airports_.find(destination) == airports_.end()) {

            throw std::invalid_argument(
                "Airport does not exist in the graph"
            );
        }

        neighbours_[origin].push_back(destination);
    }

    // Returns all successors and their transition costs
    std::vector<std::pair<AirportState, double>>
    successors(const AirportState& current) const {

        std::vector<std::pair<AirportState, double>> result;

        const auto it = neighbours_.find(
            std::string(current.get_IATA())
        );

        // No neighbours
        if (it == neighbours_.end()) {
            return result;
        }

        // Generate successor states
        for (const std::string& neighbour_IATA : it->second) {

            const AirportState& neighbour =
                airports_.at(neighbour_IATA);

            const double cost = haversine(current, neighbour);

            result.emplace_back(neighbour, cost);
        }

        return result;
    }

private:

    // Airport information indexed by IATA
    std::unordered_map<std::string, AirportState> airports_;

    // Adjacency list: IATA -> neighbours
    std::unordered_map<std::string, std::vector<std::string>>
        neighbours_;
};

} // namespace airport_search

#endif // GRAFO_HPP
