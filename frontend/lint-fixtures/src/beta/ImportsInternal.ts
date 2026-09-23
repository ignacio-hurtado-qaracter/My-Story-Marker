// expect: boundaries/dependencies
// (a) planted: a feature reaching into another feature's file.
import { alphaValue } from '../alpha/internal'

export const reached = alphaValue
