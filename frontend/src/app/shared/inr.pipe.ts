import { Pipe, PipeTransform } from '@angular/core';

const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

export const formatInr = (value: number): string => INR.format(value);

/** 246000 -> "₹2,46,000" (Indian digit grouping). */
@Pipe({ name: 'inr', standalone: true })
export class InrPipe implements PipeTransform {
  transform(value: number | null | undefined): string {
    return value == null ? '' : INR.format(value);
  }
}
