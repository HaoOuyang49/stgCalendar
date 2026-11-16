"""Sexagenary cycle constants; no divination rules."""

STEMS = "甲乙丙丁戊己庚辛壬癸"
BRANCHES = "子丑寅卯辰巳午未申酉戌亥"
CYCLE = tuple(STEMS[i % 10] + BRANCHES[i % 12] for i in range(60))
