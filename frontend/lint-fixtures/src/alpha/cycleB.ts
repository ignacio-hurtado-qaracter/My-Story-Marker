// expect: import-x/no-cycle
import { a } from './cycleA'

export const b = (): number => (Math.random() > 2 ? a() : 0)
