# Paper build. "make sync" copies the generated tables and figures from the campaign results
# (testbed/fig_final.py), set in a smaller font for the two-column page, and redraws the architecture figure; "make" builds main.pdf.
RES = ../results/testbed_prereg_final/paper
TABLES = table_main table_fedcost table_ablation table_detect table_overhead

main.pdf: main.tex refs.bib tables/*.tex figs/*.pdf
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex

sync:
	for t in $(TABLES); do sed -e 's/^\\small$$/\\footnotesize/' -e 's/tabcolsep}{4pt}/tabcolsep}{3pt}/' \
	    $(RES)/$$t.tex > tables/$$t.tex; done
	sed -i -e 's/Recall, other controllers/Recall, other ctrl./' -e 's/Lossless federated XGBoost{,} secure aggregation/Lossless, secure aggregation/' \
	    -e 's/Data sent (MB)/Data (MB)/' -e 's/Recall, Mimic/Rec., Mimic/' -e 's/Recall, other ctrl./Rec., other ctrl./' \
	    -e 's/^\\footnotesize$$/\\footnotesize\\setlength{\\tabcolsep}{4pt}/' tables/table_fedcost.tex
	sed -i 's/tabcolsep}{3pt}/tabcolsep}{2pt}/' tables/table_overhead.tex
	cp $(RES)/fig_timeline.pdf $(RES)/fig_fl_effect.pdf figs/
	~/.venvs/loft/bin/python figs/make_architecture.py

clean:
	latexmk -C main.tex

.PHONY: sync clean
