from __future__ import annotations

import importlib.util
import unittest

from tests import helpers

SCRIPTS = helpers.ROOT / "scripts"


def load_check():
    spec = importlib.util.spec_from_file_location("check_i18n", SCRIPTS / "check-i18n.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NsisLanguageCheckTest(unittest.TestCase):
    def test_nsis_key_uses_and_hardcoded_text(self) -> None:
        check = load_check()
        self.assertIn(".nsi", check.CODE_SUFFIXES)
        text = "\n".join([
            'DetailPrint "Copying files"',
            'MessageBox MB_OK "Hello there"',
            'Section "Core files" S1',
            'Section "!Required" S2',
            'SectionSetText ${S1} "Other text"',
            '!define MUI_WELCOMEPAGE_TITLE "Welcome"',
            'DetailPrint "$(installer.step.files)"',
            'Section "!$(installer.component.core)" SecCore',
            'Section "-hidden"',
            'Section "Uninstall"',
            'MessageBox MB_OK "$1"',
        ])
        flagged = [m.group(0).strip() for pattern in check.HARDCODED[".nsi"] for m in pattern.finditer(text)]
        self.assertEqual(len(flagged), 6, flagged)
        used = {key for pattern in check.KEY_USES for key in pattern.findall(text)}
        self.assertEqual(used, {"installer.step.files", "installer.component.core"})
