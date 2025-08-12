pybabel extract -F babel.cfg -o messages.pot .
pybabel update -i messages.pot -d ./translations -l en

# -k="lazy_gettext _ lazy_ngettext ngettext" 