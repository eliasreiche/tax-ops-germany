# tax-ops-feedback

Fehlerreport-Plugin für die `tax-ops`-Skills. Ein Skill (`tax-ops-feedback`) plus `pruefe_report.py` (Regex-Netz gegen Mandantendaten). Kein Executor, keine Rechenlogik.

Ablauf: ausdrückliche Fehlermeldung der Nutzerin → Report nach Whitelist-Vorlage → Regex-Prüfung → Sichtfreigabe → Versand an den Maintainer (Mail-Werkzeug oder `mailto:`). Details in [`skills/tax-ops-feedback/SKILL.md`](skills/tax-ops-feedback/SKILL.md).

Selbsttest: `python3 skills/tax-ops-feedback/pruefe_report.py --demo`
