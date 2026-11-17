# Paper build. "make sync" copies the generated tables and figures from the campaign results
# (testbed/fig_final.py) and redraws the architecture figure; "make" builds main.pdf.
RES = ../results/testbed_prereg_final/paper
TABLES = table_main table_fedcost table_ablation table_detect table_overhead

main.pdf: main.tex refs.bib tables/*.tex figs/*.pdf
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

sync:
	for t in $(TABLES); do cp $(RES)/$$t.tex tables/; done
	cp $(RES)/fig_timeline.pdf figs/
	~/.venvs/loft/bin/python figs/make_architecture.py

clean:
	latexmk -C main.tex

.PHONY: sync clean
