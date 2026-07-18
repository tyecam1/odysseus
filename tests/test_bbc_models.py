import pytest
from pydantic import ValidationError

from src.bbc.difficulty import DIFFICULTY_WEIGHTS, score_difficulty
from src.bbc.models import DifficultyComponents, Room, SCHEMA_VERSION
from src.bbc.runtime import authored_ship


def test_difficulty_is_versioned_weighted_and_banded():
    result = score_difficulty(DifficultyComponents(
        blocker_severity=100,
        blocker_count=100,
        external_dependency=100,
        cross_repository_dependency=100,
        unresolved_uncertainty=100,
        test_gap=100,
        deployment_surface=100,
        rollback_risk=100,
        implementation_complexity=100,
    ))
    assert result.score == 100
    assert result.band == "high"
    assert result.version == "1.1"
    assert result.weights == DIFFICULTY_WEIGHTS
    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_difficulty_boundaries_keep_colour_independent_of_workflow_state():
    low = score_difficulty({name: 0 for name in DIFFICULTY_WEIGHTS})
    medium = score_difficulty({name: 50 for name in DIFFICULTY_WEIGHTS})
    high = score_difficulty({name: 90 for name in DIFFICULTY_WEIGHTS})
    assert (low.score, low.band) == (0, "low")
    assert (medium.score, medium.band) == (50, "medium")
    assert (high.score, high.band) == (90, "high")


def test_blocker_count_is_an_explicit_weighted_component():
    result = score_difficulty({
        name: (4 if name == "blocker_count" else 0)
        for name in DIFFICULTY_WEIGHTS
    })
    assert result.components.blocker_count == 4
    assert "blocker_count" in result.weights
    assert sum(result.weights.values()) == pytest.approx(1.0)


def test_contracts_reject_unknown_fields():
    with pytest.raises(ValidationError):
        Room(
            id="bridge", name="Bridge", function="Pilotage", deck=1,
            position={"x": 1, "y": 1}, size={"x": 2, "y": 2}, hidden_authority=True,
        )


def test_authored_ship_is_one_deck_with_compact_stable_room_coordinates():
    ship = authored_ship()
    assert SCHEMA_VERSION == 1
    assert ship.deck_count == 1
    assert 6 <= len(ship.rooms) <= 8
    assert ship.active_room_id in {room.id for room in ship.rooms}
    assert all(0 <= room.position.x <= 100 and 0 <= room.position.y <= 92 for room in ship.rooms)
    assert all(not room.occupant_ids for room in ship.rooms)
