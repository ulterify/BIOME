# BIOME

**BIOME** stands for **Balanced Input Organizer for Microbiome Experiments**.
This repository contains a small planning tool for designing feasible soil
microbiome screening experiments with combinatorial test generation.

The intended study uses soil substrate from a potato field. That substrate is
expected to already contain a background community of organisms, including
microbes and pathogens commonly associated with potato production systems. The
experimental treatments add commercially available biostimulants, potential
soil antagonists, and soil or plant amendments. The resulting samples will be
analysed by DNA classification to compare microbial abundance and diversity
across treatment combinations.

DNA classification is expensive enough that testing every possible treatment
combination is not advisable. BIOME uses PICT pairwise and higher-order
combinatorial generation to select a smaller experimental test set that still
covers many meaningful combinations of inputs. It optimizes the test setup, not
the soil treatment itself.

The project is currently in the proposal phase. If the budget is approved and
the experiment proceeds, the PICT model can be amended with more precise
constraints from the actual test setup, available materials, replication plan,
greenhouse or field logistics, and sample budget.

## Experimental Design Context

The current model represents each candidate additive as a binary factor:

- `biostimulant_1`, `biostimulant_2`, `biostimulant_3`
- `antagonist_1`, `antagonist_2`, `antagonist_3`
- `amendment_1`, `amendment_2`, `amendment_3`

Each factor can be either `yes` or `no`, meaning that the additive is either
included or not included in a given sample.

The current base model also requires at least one antagonist:

```text
[antagonist_1] = "yes" OR [antagonist_2] = "yes" OR [antagonist_3] = "yes";
```

The scripts can add generated constraints for "at most N additives are present".
This is useful because high-additive mixtures may become unrealistic, hard to
interpret biologically, or too expensive to execute.

O18, oxygen-18 isotope tracing, is planned as a later mechanistic tool. The
initial combinatorial design helps identify treatment combinations where an
effect is observed; O18 can then support follow-up analysis of how the additives
may be working.

## Why PICT

PICT generates covering arrays. Instead of testing the full factorial design, it
selects a smaller set of rows that cover interactions up to a chosen strength.

In this repository:

- `order` is the interaction strength passed to PICT with `/o:N`.
- `max-yes` is the maximum number of yes-valued additives allowed in any test.
- `iterations` is the number of PICT seed attempts passed with `/b:N`.
- `seed` is the base random seed passed with `/r:N`.

For example, order `2` covers every valid pairwise interaction. Higher orders
cover larger interactions, but generally require more samples.

## Repository Layout

- `pict-model.txt`: base PICT model for the additive factors and fixed
  constraints.
- `generate-max-yes-constraints.py`: prints generated PICT constraints for an
  "at most N yes values" rule.
- `generate-pict-testsets.py`: generates concrete PICT test set TSV files for
  one `max-yes` value and one or more orders.
- `generate-pict-test-count-table.py`: evaluates many `max-yes` and `order`
  combinations, then writes a count table and visualisation files.
- `pict_common.py`: shared parsing, constraint generation, PICT execution, and
  output helpers.
- `templates/plotly_count_surface.html.j2`: Plotly HTML template for interactive
  sample-count visualisation.
- `pict-testsets/`: generated test sets, count tables, plots, and model variants.

## Requirements

Install or provide:

- Python 3.11 or newer
- `jinja2`
- Microsoft PICT command-line executable
- `gnuplot`, only needed for SVG plot generation from
  `generate-pict-test-count-table.py`

The scripts default to a local PICT binary at:

```text
/home/thomas/source/pict/build/cli/pict
```

Use `--pict-bin` if PICT is installed elsewhere.

## Basic Usage

Show generated max-yes constraints:

```bash
./generate-max-yes-constraints.py 4 pict-model.txt
```

Generate test sets for orders 2, 3, 4, and 5 with at most 4 included additives:

```bash
./generate-pict-testsets.py --max-yes 4 --orders "2 3 4 5"
```

Generate a sample-count table and plots across multiple design choices:

```bash
./generate-pict-test-count-table.py \
  --max-yes-values "1 2 3 4 5 6 7 8 9" \
  --orders "2 3 4 5"
```

Use explicit PICT location:

```bash
./generate-pict-testsets.py \
  --pict-bin /path/to/pict \
  --max-yes 4 \
  --orders "2 3 4 5"
```

## Outputs

Generated files are written to `pict-testsets/` by default.

Test set files are named like:

```text
order-3.max-yes-4.tsv
```

Each row is one proposed treatment combination. Each column is one additive
factor with value `yes` or `no`.

Count-table runs produce files named like:

```text
test-counts.orders-2_3_4_5.max-yes-1_2_3_4_5_6_7_8_9.tsv
test-counts.orders-2_3_4_5.max-yes-1_2_3_4_5_6_7_8_9.svg
test-counts.orders-2_3_4_5.max-yes-1_2_3_4_5_6_7_8_9.html
test-counts.orders-2_3_4_5.max-yes-1_2_3_4_5_6_7_8_9.vtp
```

The TSV table is the most direct planning output. The SVG, HTML, and VTK outputs
help visualise the tradeoff between interaction order, maximum mixture size, and
sample count.

## Choosing a Design

Use the count table to find a practical balance:

- Lower `order` means fewer samples but less interaction coverage.
- Higher `order` means stronger combinatorial coverage but more samples.
- Lower `max-yes` excludes complex mixtures, but it does not always reduce the
  generated sample count. For example, in
  `pict-testsets/test-counts.orders-2_3_4_5.max-yes-1_2_3_4_5_6_7_8_9.tsv`,
  `order_2` requires 21 tests at `max_yes=2`, 18 tests at `max_yes=3`, and 10
  tests at `max_yes=4`.
- Higher `max-yes` allows more additive-rich combinations but increases sample
  count and may reduce biological interpretability.

During proposal writing, BIOME can justify why the experiment samples a
systematic subset instead of the full factorial design. During execution, the
same model can be updated with real constraints before generating the final
sample list.

## Updating the Model

Edit `pict-model.txt` when additives or constraints change.

Typical proposal-to-experiment updates may include:

- replacing placeholder additive names with actual product or strain names
- requiring positive and negative controls
- excluding incompatible additives
- limiting combinations that are chemically, biologically, or logistically
  unrealistic
- adding blocking, batch, or substrate factors
- adding O18-related conditions if isotope tracing is included in the same
  classification design

After changing the model, regenerate the count table first. This shows whether
the resulting design is still feasible before producing final test sets.

```bash
./generate-pict-test-count-table.py --orders "2 3 4 5" --max-yes-values "1 2 3 4 5"
```

Then generate the selected design:

```bash
./generate-pict-testsets.py --max-yes 4 --order 3
```

## Notes

PICT designs optimise combinatorial coverage. They do not replace biological
replication, randomisation, blocking, or laboratory quality controls. Those
parts of the experimental design should be decided separately and then reflected
in `pict-model.txt` where they affect valid treatment combinations.
