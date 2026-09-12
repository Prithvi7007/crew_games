from app.db import get_game_content

QUIZ = {
    "theme": "Universal Worlds",
    "questions": (
        {"prompt": "In Despicable Me, who is the Minions' longtime boss?", "options": ["Gru", "Vector", "Dr. Nefario", "El Macho"], "answer": 0},
        {"prompt": "What kind of creature is Toothless in How to Train Your Dragon?", "options": ["Griffin", "Dragon", "Phoenix", "Wolf"], "answer": 1},
        {"prompt": "Which faction does Optimus Prime lead?", "options": ["Decepticons", "Maximals", "Autobots", "Predacons"], "answer": 2},
        {"prompt": "What is the name of the school attended by Harry Potter?", "options": ["Beauxbatons", "Durmstrang", "Ilvermorny", "Hogwarts"], "answer": 3},
        {"prompt": "Shrek prefers to live in what kind of place?", "options": ["A swamp", "A castle", "A tower", "A village"], "answer": 0},
        {"prompt": "Jurassic World stories center on animals from which group?", "options": ["Dinosaurs", "Mammoths", "Sharks", "Dragons"], "answer": 0},
        {"prompt": "What fruit is famously associated with the Minions?", "options": ["Apple", "Banana", "Orange", "Pineapple"], "answer": 1},
        {"prompt": "What is Optimus Prime's home planet?", "options": ["Krypton", "Cybertron", "Vulcan", "Pandora"], "answer": 1},
        {"prompt": "What species is Shrek?", "options": ["Troll", "Goblin", "Ogre", "Giant"], "answer": 2},
        {"prompt": "The Jurassic franchise is best known for bringing which extinct creatures back to life?", "options": ["Dinosaurs", "Dodos", "Sabertooth cats", "Trilobites"], "answer": 0},
    ),
}


def get_quiz(game_day):
    scheduled = get_game_content("trivia", game_day.isoformat(), published_only=True)
    if scheduled:
        raw_questions = scheduled["content"].get("questions") or []
        questions = []
        for item in raw_questions:
            prompt = str(item.get("prompt") or "").strip()
            options = tuple(str(option).strip() for option in (item.get("options") or []))
            try:
                answer = int(item.get("answer"))
            except (TypeError, ValueError):
                answer = -1
            if prompt and len(options) == 4 and answer in range(4):
                questions.append({"prompt": prompt, "options": options, "answer": answer})
        if len(questions) == 10:
            return {"theme": scheduled["theme_label"], "questions": tuple(questions)}
    return QUIZ
