from app.db import get_db, get_game_content
from app.mystery.game import score_for_clues


def test_question_bank_import_dry_run_and_publish(app):
    runner = app.test_cli_runner()

    dry_run = runner.invoke(args=["import-question-bank", "--dry-run"])
    assert dry_run.exit_code == 0, dry_run.output
    assert "127 created" in dry_run.output

    with app.app_context():
        row = get_db().execute("SELECT COUNT(*) AS count FROM game_content").fetchone()
        assert int(row["count"]) == 0

    result = runner.invoke(args=["import-question-bank"])
    assert result.exit_code == 0, result.output
    assert "127 created" in result.output

    with app.app_context():
        row = get_db().execute("SELECT COUNT(*) AS count FROM game_content").fetchone()
        assert int(row["count"]) == 127

        mystery = get_game_content("mystery", "2026-09-21", published_only=True)
        assert mystery["content"]["source_id"] == "MM001"
        assert mystery["content"]["answer"] == "Jurassic Park"
        assert len(mystery["content"]["clues"]) == 4

        trivia = get_game_content("trivia", "2026-09-22", published_only=True)
        assert trivia["content"]["source_week"] == 1
        assert len(trivia["content"]["questions"]) == 10
        first = trivia["content"]["questions"][0]
        assert first["source_id"] == "FB2-214"
        assert first["options"][first["answer"]] == "Frosted Flakes"
        assert len({question["answer"] for question in trivia["content"]["questions"]}) > 1


def test_question_bank_import_is_idempotent_without_replace(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["import-question-bank"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(args=["import-question-bank"])
    assert second.exit_code == 0, second.output
    assert "0 created" in second.output
    assert "127 skipped existing" in second.output


def test_four_clue_mystery_scores_stay_within_crew_100_point_cap():
    assert [score_for_clues(index, 4) for index in range(1, 5)] == [100, 75, 50, 25]
