# ADR 0001: Stabilize payment composition encoding

- Status: Accepted
- Date: 2026-07-26

## Context

The payment composition chart supports gross-interest and after-subsidy views. Altair previously inferred the stacked-area order and categorical color domain from the components present in each view. This placed the flat scheduled-principal band away from the baseline and allowed a component's color to change when the Subsidy component was hidden.

The chart should remain easy to compare when the user switches **Show interest after subsidy**, while continuing to use the active Streamlit theme.

## Decision

Use this canonical bottom-to-top component order:

1. Scheduled principal
2. Recurring overpayment
3. Lump sum
4. Fees
5. Interest after subsidy
6. Subsidy, when displayed

Attach an explicit numeric order to each chart row and use Altair's `order` encoding instead of relying on source-row or inferred category order.

Use the complete canonical component list as the categorical color domain in both chart modes. Do not define a color range: Streamlit's active theme continues to supply the palette, while the fixed domain keeps each shared label mapped to the same theme color. Restrict legend values to the components visible in the selected mode so Subsidy is omitted from the after-subsidy legend.

This decision affects visualization projection only. Mortgage calculations, reporting data, totals, CSV output, tooltips, and chart interactions remain unchanged.

## Consequences

- Scheduled principal forms the stable bottom band of the stacked area chart.
- Shared components retain their colors when the subsidy toggle changes the visible dataset.
- Chart colors continue to adapt to the active Streamlit theme instead of using fixed hexadecimal values.
- Adding or reordering payment components requires updating the canonical sequence deliberately.

## Alternatives considered

### Freeze component colors

Assigning explicit hexadecimal colors would guarantee stable mappings, but it would prevent the chart from following future light, dark, or custom Streamlit themes.

### Use an inferred color domain

Allowing Altair to derive the domain from visible data is simpler, but component-to-color mappings may change when a category is omitted or introduced.

### Rely on source-row order

Reordering projected rows could influence the current rendering, but it leaves the intended stack order implicit and dependent on Vega-Lite behavior. An explicit order encoding makes the decision part of the chart specification.
