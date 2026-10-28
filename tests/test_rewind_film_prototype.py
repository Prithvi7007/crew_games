"""CREW Rewind Film Lab: score-driven visuals, permission gate, real season data."""
from datetime import date
from pathlib import Path

from app.db import create_profile, finalize_game_stats, get_season_for_date, profile_user_key
from app.season_rewind import build_season_rewind
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "frontend/src/player/main.jsx").read_text()
FILM = (ROOT / "frontend/src/player/RewindFilmPrototype.jsx").read_text()
CSS = (ROOT / "frontend/src/player/styles/rewind-film.css").read_text()
ROUTE = (ROOT / "app/main/routes.py").read_text()


def test_prototype_is_server_gated_and_live_rewind_is_still_default():
    assert 'request.args.get("prototype") == "1"' in ROUTE
    assert 'user.get("role") in ("admin", "owner")' in ROUTE
    assert "if film_requested and not film_preview:" in ROUTE
    assert 'rewindFilmPrototype": film_preview' in ROUTE
    assert "data.rewindFilmPrototype === true" in MAIN
    assert "RewindFilmPrototype : pages[root.dataset.page]" in MAIN
    assert "rewind:SeasonRewind" in MAIN
    assert "/rewind?preview=1" in FILM


def test_weekly_race_uses_real_cutoff_scoped_game_scores(app):
    with app.app_context():
        season = get_season_for_date(date(2026, 10, 26))
        profile = create_profile(
            "FilmTester", generate_password_hash("test-test-test"),
            "⭐", generate_password_hash("test-key"),
        )
        pid = int(profile["id"])
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-22", 85, True)
        finalize_game_stats(profile_user_key(pid), "word", "2026-09-23", 70, True)
        finalize_game_stats(profile_user_key(pid), "trivia", "2026-09-29", 92, True)
        data = build_season_rewind(pid, season, admin_preview=True)

    assert len(data["weeklyGameScores"]) == 6
    assert data["weeklyGameScores"][0]["games"]["trivia"] == 85
    assert data["weeklyGameScores"][0]["games"]["word"] == 70
    assert data["weeklyGameScores"][1]["games"]["trivia"] == 92
    assert data["weeklyGameScores"][2]["games"]["mystery"] == 0
    assert sum(sum(item["games"].values()) for item in data["weeklyGameScores"]) == data["points"] == 247


def test_game_visuals_follow_weekly_scores_not_fake_keyframes():
    assert "history" not in FILM or "weeklyGameScores" in FILM
    assert "const weeks = recap.weeklyGameScores || []" in FILM
    assert "weeks.slice(0, limit + 1)" in FILM
    assert "(game.score/maximum)*(compact ? 252 : 600)" in FILM
    assert "rankingY[game.key]" in FILM
    assert "duration:(end-from)*2.15, ease:'linear'" in FILM
    assert "const theme = GAMES[phase==='discovery' ? lead : phase==='race' ? liveLeader : null]" in FILM
    assert "leadChanges += 1" in FILM
    assert "game.score === topScore" in FILM or "item.score === topScore" in FILM
    assert "<m.path" in FILM
    assert "<m.circle" in FILM
    assert "animate={{cx:targetX,cy:targetY" in FILM
    assert "Math.round(100 * topScore / total)" in FILM
    assert "setTimeout" in FILM
    assert 'phase === "race"' not in FILM or "phase" in FILM
    assert "useReducedMotion()" in FILM
    assert "if (reduce || weeks.length<2 || discovery.noGames)" in FILM
    assert "aria-current={phase==='race'&&week===i?'step':undefined}" in FILM


def test_film_is_single_continuous_stage_not_a_seven_panel_dashboard():
    assert "viewBox={compact ? '0 0 430 440' : '0 0 940 480'}" in FILM
    assert 'className="rewind-film-impact"' in FILM
    assert ".rewind-film-discovery-copy .rewind-film-impact" in CSS
    assert "rewind-film-field" in FILM
    assert "rewind-film-discovery-copy" in FILM
    assert "7 CHAPTERS" not in FILM
    assert "ORIGINAL SERIES" not in FILM
    assert "rewind-film-line" not in CSS
    assert "rewind-film-timeline button" in CSS
    assert ".rewind-film-arena > svg" in CSS


def test_opening_symbols_have_distinct_positions_and_labels_below_them():
    # Catch the layout regression visible in the owner screenshot: game labels
    # should never share the center coordinate of their symbols.
    assert "[125,355,585,815]" in FILM
    assert "[62,164,266,368]" in FILM
    assert "const introY=compact ? 197 : 240" in FILM
    assert "<text x={targetX} y={targetY+" in FILM
    assert "phase==='intro'?(compact?62:83)" in FILM
    assert "textAnchor=\"middle\"" in FILM
    assert "rewind-film-arena-intro > svg text" in CSS


def test_rewind_restores_personal_story_after_the_game_race():
    assert "phase==='identity'" in FILM
    assert "phase==='trophy'" in FILM
    assert "phase==='finale'" in FILM
    assert "const style = insights.playStyle" in FILM
    assert "const momentum = insights.momentum" in FILM
    assert "insights.highestGame" in FILM
    assert "recap.badges?.featured" in FILM
    assert "<BadgeMedallion badge={trophy}" in FILM
    assert "(trophy?'trophy':'finale')" in FILM  # no fake award if none was earned
    assert "recap.champion" in FILM
    assert "onClick={shareStory}" in FILM
    assert "navigator.share" in FILM
    assert ".rewind-film-personality" in CSS
    assert ".rewind-film-award" in CSS
    assert ".rewind-film-finale-object" in CSS
    assert ".rewind-film-timeline[hidden]" in CSS


def test_other_player_film_preview_is_marked_private_and_cannot_share():
    assert 'const previewPlayer = data.rewindPreviewPlayer;' in FILM
    assert '"VIEWING " + previewPlayer + " · PRIVATE PREVIEW"' in FILM
    assert '!previewPlayer && <button className="rewind-film-primary"' in FILM
    assert 'onClick={shareStory}' in FILM


def test_badge_art_is_not_hidden_by_race_svg_selectors():
    # The old descendant selector hid the SVG inside the earned badge.
    # Only the race canvas's direct SVG can be faded during the badge reveal.
    assert ".rewind-film-arena-trophy > svg" in CSS
    assert ".rewind-film-arena-trophy svg" not in CSS
    assert ".rewind-film-arena svg {" not in CSS
    assert ".rewind-film-arena > svg" in CSS
    assert ".rewind-film-trophy .rewind-film-award .trophy-medallion > svg" in CSS
    assert "<BadgeMedallion badge={trophy}" in FILM


def test_badge_name_and_story_use_separate_layout_regions():
    # The medallion itself is a direct span, so a generic >span text
    # rule also incorrectly overrides its inherited emblem colors.
    assert 'className="rewind-film-award-name"' in FILM
    assert 'className="rewind-film-award-meta"' in FILM
    assert ".rewind-film-award>span {" not in CSS
    assert ".rewind-film-award>.rewind-film-award-name" in CSS
    assert ".rewind-film-trophy .rewind-film-story-beat" in CSS
    assert ".rewind-film-trophy .rewind-film-arena" in CSS
    assert ".rewind-film-trophy .rewind-film-controls" in CSS

def test_weekly_race_is_continuous_not_a_sequence_of_timeouts():
    assert "export function filmFrame(weeks, progress, lanes)" in FILM
    assert "const controls=animate(from,end" in FILM
    assert "onUpdate:value=>" in FILM
    assert "progressRef.current=value;" in FILM
    assert "setProgress(value);" in FILM
    assert "const t = Math.max(0,Math.min(1,progress-lower))" in FILM
    assert "score:mix(a.find(g=>g.key===key).score,b.find(g=>g.key===key).score,t)" in FILM
    assert "y:mix(lanes[first],lanes[next],easeAcross(t))" in FILM
    assert "controls.stop()" in FILM
    assert "seek(i)" in FILM
    assert "setInterval(" not in FILM
    assert "leadChanged ? 1650 : 1150" not in FILM
    assert "scoreSnapshot.map(g=>" in FILM  # static accessible labels; no 60 Hz announcements
    assert ".rewind-film-race .rewind-film-timeline::before" in CSS


def test_actual_weekly_scores_drive_story_beats_without_made_up_analytics():
    assert "export function filmWeekBeat(weeks, index)" in FILM
    assert "Number(row.games?.[key])||0" in FILM
    assert "The lead changed." in FILM
    assert "A new weekly high." in FILM
    assert "You scored in " in FILM
    assert "No points were recorded this week." in FILM
    assert "weekBeat.detail" in FILM
    assert "insights.peerComparison" in FILM
    assert "insights.longestWeeklyStreak" in FILM
    assert "insights.highestGame" in FILM
    assert "insights.outpacedPercent" in FILM
    assert "personalFindings.map" in FILM
    assert 'className="rewind-film-week-finding"' in FILM
    assert ".rewind-film-week-finding" in CSS
