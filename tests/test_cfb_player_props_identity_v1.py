from __future__ import annotations


def test_official_espn_athlete_id_is_canonical_and_provider_id_is_alias_only():
    import cfb_player_props_identity_v1 as identity

    player = identity.player_identity_from_roster_row(
        {"id": "12345", "fullName": "Jalen Example", "position": {"abbreviation": "QB"}},
        official_team_id="77",
        team_name="Example State",
        team_abbr="EXS",
    )
    assert player is not None
    assert player.official_player_id == "12345"
    assert player.official_team_id == "77"
    assert player.canonical_name == "Jalen Example"
    assert player.position == "QB"

    aliased = identity.with_provider_alias(player, "SportsGameOdds", "sgo-player-9")
    assert aliased.official_player_id == "12345"
    assert ("sportsgameodds", "sgo-player-9") in aliased.provider_aliases


def test_exact_provider_alias_or_exact_team_name_can_resolve_but_name_only_cannot():
    import cfb_player_props_identity_v1 as identity

    base = identity.player_identity_from_roster_row(
        {"id": "12345", "displayName": "Jalen Example", "position": {"abbreviation": "QB"}},
        official_team_id="77",
        team_name="Example State",
        team_abbr="EXS",
    )
    base = identity.with_provider_alias(base, "SportsGameOdds", "sgo-player-9")
    index = identity.build_identity_index([base])

    assert identity.resolve_player_identity(
        {"provider": "SportsGameOdds", "provider_player_id": "sgo-player-9"}, index
    ) == base
    assert identity.resolve_player_identity(
        {"player_name": "Jalen Example", "official_team_id": "77"}, index
    ) == base
    assert identity.resolve_player_identity({"player_name": "Jalen Example"}, index) is None
    assert identity.resolve_player_identity(
        {"player_name": "J. Example", "official_team_id": "77"}, index
    ) is None


def test_ambiguous_same_name_team_key_is_not_certified():
    import cfb_player_props_identity_v1 as identity

    p1 = identity.CanonicalPlayerIdentity("1", "77", "Alex Smith", "WR", "Example State", "EXS", ())
    p2 = identity.CanonicalPlayerIdentity("2", "77", "Alex Smith", "RB", "Example State", "EXS", ())
    index = identity.build_identity_index([p1, p2])
    assert identity.resolve_player_identity(
        {"player_name": "Alex Smith", "official_team_id": "77"}, index
    ) is None
    assert identity.resolve_player_identity({"official_player_id": "1"}, index) == p1


def test_roster_row_without_official_player_or_team_id_fails_closed():
    import cfb_player_props_identity_v1 as identity

    assert identity.player_identity_from_roster_row(
        {"fullName": "No ID"}, official_team_id="77", team_name="Example State"
    ) is None
    assert identity.player_identity_from_roster_row(
        {"id": "123"}, official_team_id="", team_name="Example State"
    ) is None
