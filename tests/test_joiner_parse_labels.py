from attackiq_cli.joiner.parse_labels import parse_labels


def test_parse_labels_extracts_explicit_tokens():
    labels = "T1003, TA0001, DET0001, tool::mimikatz, PR.AC, ignore"
    parsed = parse_labels(labels)

    assert parsed.techniques == ["T1003"]
    assert parsed.tactics == ["TA0001"]
    assert parsed.detection_strategy_ids == ["DET0001"]
    assert parsed.tools == ["tool::mimikatz"]
    assert parsed.csf == ["PR.AC"]


def test_parse_labels_respects_delimiter():
    labels = "T1003,T1059"
    parsed = parse_labels(labels)

    assert parsed.techniques == []

