from __future__ import annotations

from coworker.apps.script_murder.case_loader import load_case


def test_case_package_has_complete_authorized_references() -> None:
    case = load_case()

    assert case.case_id == "shadow_of_the_elysee"
    assert len(case.characters) == 5
    assert len(case.documents) == 12
    assert set(case.public_cast) == set(case.characters)
    assert set(case.deliveries) == {1, 2}

    andre_round_two = {item.document_id for item in case.documents_for(2, "andre_robespierre")}
    marie_round_two = {item.document_id for item in case.documents_for(2, "marie_desmoulins")}
    assert andre_round_two == {"r2_andre_camille_witness"}
    assert marie_round_two == {"r2_marie_mole_father"}
    assert "r2_emilie_affair_reveal" not in andre_round_two
    assert "r2_andre_camille_witness" not in marie_round_two
