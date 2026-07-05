import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Standard clsx + tailwind-merge combinator for conditional Tailwind class strings. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
