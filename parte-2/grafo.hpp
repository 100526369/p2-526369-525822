#ifndef GRAFO_HPP
#define GRAFO_HPP

#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <string>
#include <string_view>
#include <unordered_map>
#include <utility>
#include <vector>

#include "estado.hpp"

namespace airport_search {

class AirportGraph {
public:
    // A reachable airport together with the cost of the fly operator
    using Successor = std::pair<AirportState, double>;

    // Adds an airport. If the IATA code already exists, it is overwritten.
    void add_airport(const AirportState& airport) {
        airports_.insert_or_assign(
            normalize(airport.get_IATA()),
            airport
        );
    }

    // Adds a directed connection. The cost is computed once here, since
    // the distance between two airports never changes.
    void add_neighbour(std::string_view from, std::string_view to) {
        const std::string origin = normalize(from);
        const std::string destination = normalize(to);

        const auto from_it = airports_.find(origin);
        const auto to_it = airports_.find(destination);

        if (from_it == airports_.end() || to_it == airports_.end()) {
            throw std::invalid_argument(
                "Airport does not exist in the graph"
            );
        }

        // A flight to the same airport never helps and would only
        // add useless successors
        if (origin == destination) {
            return;
        }

        std::vector<Successor>& list = neighbours_[origin];

        // Several flights can join the same pair of airports; for this
        // part only the pair matters, so keep it once
        const bool already_present = std::any_of(
            list.begin(), list.end(),
            [&](const Successor& s) { return s.first == to_it->second; }
        );
        if (already_present) {
            return;
        }

        list.emplace_back(
            to_it->second,
            haversine(from_it->second, to_it->second)
        );
    }

    bool contains(std::string_view code) const {
        return airports_.find(normalize(code)) != airports_.end();
    }

    // Used to build the initial and goal states from the input file
    const AirportState& get_airport(std::string_view code) const {
        const auto it = airports_.find(normalize(code));
        if (it == airports_.end()) {
            throw std::invalid_argument(
                "Unknown IATA code: " + std::string(code)
            );
        }
        return it->second;
    }

    // Implements the fly operator: every reachable state with its cost.
    // Returns a reference so no copies are made on each expansion.
    const std::vector<Successor>&
    successors(const AirportState& current) const {
        static const std::vector<Successor> none;

        const auto it = neighbours_.find(std::string(current.get_IATA()));
        return it == neighbours_.end() ? none : it->second;
    }

private:
    static std::string normalize(std::string_view code) {
        std::string result(code);
        for (char& c : result) {
            c = static_cast<char>(
                std::toupper(static_cast<unsigned char>(c))
            );
        }
        return result;
    }

    // Airport information indexed by IATA
    std::unordered_map<std::string, AirportState> airports_;

    // Adjacency list: IATA -> successors (state + precomputed cost)
    std::unordered_map<std::string, std::vector<Successor>> neighbours_;
};

} // namespace airport_search

#endif // GRAFO_HPP