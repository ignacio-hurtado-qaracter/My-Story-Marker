// expect: boundaries/dependencies
// (g) planted: app/ reaching into a feature's file.
import { alphaValue } from '../alpha/internal'

export const appReached = alphaValue
