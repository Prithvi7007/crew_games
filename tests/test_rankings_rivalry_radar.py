"""Functional Rivalry Radar tests using the source's actual pure JavaScript model."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_matchup_model_handles_nearest_rivals_manual_choices_and_unranked_players():
    program = """
import assert from 'node:assert/strict';
import { rivalryModel } from './frontend/src/player/rankingsRivalry.js';

const alice = {profile_id: 1, username:'Alice', rank:1, points:150, completed:3};
const bob = {profile_id: 2, username:'Bob', rank:2, points:130, completed:4, me:true};
const carol = {profile_id: 3, username:'Carol', rank:3, points:105, completed:2};
const board = {players:[alice,bob,carol], me:bob};
const snapshot=JSON.stringify(board);

const nearby = rivalryModel(board);
assert.equal(nearby.rival.profile_id, 1);
assert.equal(nearby.direction, 'behind');
assert.equal(nearby.summary, '20 points to tie');
assert.equal(nearby.gap, 20);
assert.equal(rivalryModel(board, 3).rival.username,'Carol');
assert.equal(rivalryModel(board, '3').summary,"You're 25 points ahead");
assert.equal(rivalryModel(board, 2).rival.profile_id,1);  // never compare to yourself
assert.equal(rivalryModel(board, 999).rival.profile_id,1);
assert.equal(JSON.stringify(board),snapshot); // no board mutations or stored rival

const leader = {players:[alice,bob,carol], me:alice};
assert.equal(rivalryModel(leader).rival.profile_id,2); // closest challenger
const newcomer = {profile_id:4, username:'New', rank:null, points:0, completed:0, me:true};
assert.equal(rivalryModel({players:[alice,bob,carol],me:newcomer}).rival.profile_id,3);
assert.equal(rivalryModel({players:[alice],me:newcomer}).summary,'150 points to tie');

const tieA = {...alice,points:130};
const tie = rivalryModel({players:[tieA,bob,carol],me:bob});
assert.equal(tie.direction,'tied');
assert.equal(tie.summary,'Tied on points');
assert.equal(tie.gap,0);

const onePoint = rivalryModel({players:[{...alice,points:131},bob],me:bob});
assert.equal(onePoint.summary,'1 point to tie');
assert.equal(rivalryModel({players:[],me:newcomer}),null);
assert.equal(rivalryModel({players:[alice]}),null);
assert.equal(rivalryModel({players:[bob],me:bob}),null);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", program],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
    )
    assert result.returncode == 0, result.stderr


def test_rivalry_ui_follows_filtered_rankings_without_new_api_or_hidden_badges():
    source = (ROOT / "frontend/src/player/main.jsx").read_text(encoding="utf-8")
    component = (ROOT / "frontend/src/player/RankingsRivalry.jsx").read_text(encoding="utf-8")
    css = (ROOT / "frontend/src/player/styles/rankings-rivalry.css").read_text(encoding="utf-8")
    assert "const matchup=rivalryModel(board,rivalId)" in source
    assert "setBoard(payload);" in source
    assert "setRivalId(null);" in source
    assert '<RankingsRivalry matchup={matchup} panelRef={rivalryRef}/>' in source
    assert "aria-pressed={String(matchup?.rival.profile_id)===String(player.profile_id)}" in source
    assert "!player.me && !player.unranked && board.me" in source
    assert "prefers-reduced-motion: reduce" in source
    assert "EquippedProfileBadge badge={player.equippedBadge}" in component
    assert "role=\"status\" aria-live=\"polite\"" in component
    assert "Matchups never change points, badges or standings." in component
    assert "@media (max-width:620px)" in css
