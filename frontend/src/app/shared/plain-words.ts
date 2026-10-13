/** Plain names for the insurer's jargon, shown next to the insurer's own words. */
export function plainCutName(label: string, reason = ''): string {
  const t = `${label} ${reason}`.toLowerCase();
  if (/room|proportion/.test(t)) return 'Room cost above your limit';
  if (/consumable|non-?payable|gloves|ppe|\bkits?\b/.test(t)) return 'Items your policy never pays for';
  if (/co-?pay/.test(t)) return 'Your share of the bill (co-pay)';
  if (/sub-?limit|\bcap(ped)?\b/.test(t)) return 'Above the limit for this treatment';
  if (/deductible/.test(t)) return 'Amount you pay first (deductible)';
  if (/not covered|exclu/.test(t)) return 'Not covered by your policy';
  if (/no reason|other deduction|unspecified|miscellaneous/.test(t)) return 'Cut with no reason given';
  return label;
}
