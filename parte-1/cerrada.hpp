#ifndef CERRADA_HPP
#define CERRADA_HPP

#include <cstddef>
#include <unordered_set>

#include "estado.hpp"

namespace airport_search {

// States are identified by their IATA codes.
class ClosedList {
public:
    bool contains(const AirportState& state) const {
        return states_.find(state) != states_.end();
    }

    //returns true if state wasn't already there
    bool insert(const AirportState& state) {
        return states_.insert(state).second;
    }

    bool empty() const {
        return states_.empty();
    }

    std::size_t size() const {
        return states_.size();
    }

    void reserve(std::size_t number_of_airports) {
        states_.reserve(number_of_airports);
    }

private:
    std::unordered_set<AirportState> states_;
};

} // namespace airport_search

#endif