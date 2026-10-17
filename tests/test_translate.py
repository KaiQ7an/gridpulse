from gridpulse.radio.translate import only_placeholders, protect, restore, sentences, tidy


def test_protect_swaps_f1_terms_for_placeholders():
    text, mapping = protect("Box, box. Stay out, P2 is in turn three on softs. Copy.")
    assert "box" not in text.lower() and "stay out" not in text.lower()
    assert sorted(mapping.values()) == sorted(["第2位", "3号弯", "进站，进站", "留在赛道上", "软胎", "收到"])
    assert restore(text, mapping).startswith("进站，进站 .")


def test_pit_lane_is_not_a_pit_stop():
    _, mapping = protect("Watch the pit lane speed. Pit this lap.")
    assert set(mapping.values()) == {"维修通道", "进站"}


def test_tidy_cleans_model_output():
    assert tidy("进站，进站 (英语).进站本圈为硬胎.") == "进站，进站。进站本圈为硬胎。"
    assert tidy("差距 到 勒克莱尔 为2.5秒.") == "差距到勒克莱尔为2.5秒。"


def test_only_placeholders_and_sentences():
    assert only_placeholders("ZX1 , ZX2 .")
    assert not only_placeholders("ZX1 this lap")
    assert sentences("Box, box. Copy? Yes!") == ["Box, box.", "Copy?", "Yes!"]
