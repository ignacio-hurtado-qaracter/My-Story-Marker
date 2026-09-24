// expect: import-x/no-cycle
// (d) planted: cycleA imports cycleB, which imports cycleA.
import { b } from './cycleB'

export const a = (): number => b() + 1
