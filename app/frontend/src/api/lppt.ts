import type { AircraftType, Category, Stand } from '../types'

/*
 * LPPT stands from the NAV Portugal eAIP, AD 2.24.02 "Aircraft parking / docking chart",
 * pages 1 to 8, AIRAC 006-26, effective 06-AUG-2026:
 *   https://ais.nav.pt/wp-content/uploads/AIS_Files/eAIP_Current/eAIP_Online/eAIP/graphics/eAIP/LP_AD_2_LPPT_02-{1,3,5,7}_en.pdf
 *
 * The AIP gives, per stand, the "critical" aircraft: either a named type or an ICAO code letter.
 * Our restriction is wingspan: an aircraft fits a stand when its wingspan is <= the stand limit.
 *   - named critical type: limit = that type's wingspan (CRITICAL_WINGSPAN_M)
 *   - "Code X": limit = upper bound of that ICAO code letter (CODE_LIMIT_M)
 * The AIP does NOT list wingspans. Those figures are public manufacturer values typed in by us
 * and must be checked before the report cites them. Merged cells in the AIP table were read
 * from the rendered chart; recheck 411 (Code C, merged with 405) and 426 (Code C, merged with 501).
 */

export const CODE_LIMIT_M: Record<Category, number> = { A: 15, B: 24, C: 36, D: 52, E: 65, F: 80 }

/** ICAO aerodrome reference code letter from wingspan (Annex 14). */
export function categoryOf(wingspanM: number): Category {
  const order: Category[] = ['A', 'B', 'C', 'D', 'E', 'F']
  return order.find((c) => wingspanM < CODE_LIMIT_M[c]) ?? 'F'
}

const CRITICAL_WINGSPAN_M: Record<string, number> = {
  'ATR72-600': 27.05,
  'E195 LR': 28.72,
  'A321NEO': 35.8,
  'A321-200': 35.8, // with sharklets; the AIP does not say
  'B737-800': 35.8,
  'B737-900': 35.8,
  'B757-200': 38.05,
  'B757-200W': 41.1,
  'B757-300W': 41.1,
  'A310-300': 43.9,
  'B767-300ER': 47.57,
  'B767-300ERW': 51.9,
  'B767-400ER': 51.92,
  'B777-200': 60.93,
  'A330-300': 60.3,
  'A330-900NEO': 64.0,
  'B747-400': 64.4,
  'B777-300ER': 64.8,
  'AN124-100': 73.3,
}

const CODE_NAMES: Record<string, Category> = { 'Code C': 'C', 'Code D': 'D', 'Code E': 'E', 'Code F': 'F' }

function stand(id: string, apron: string, critical: string): Stand {
  const code = CODE_NAMES[critical]
  const maxWingspanM = code ? CODE_LIMIT_M[code] : CRITICAL_WINGSPAN_M[critical]
  if (maxWingspanM === undefined) throw new Error(`Unknown critical aircraft: ${critical}`)
  return {
    id,
    name: `Stand ${id}`,
    apron,
    critical,
    category: code ?? categoryOf(maxWingspanM),
    maxWingspanM,
  }
}

const group = (apron: string, critical: string, ids: string[]) => ids.map((id) => stand(id, apron, critical))
const ids = (from: number, to: number) => Array.from({ length: to - from + 1 }, (_, i) => String(from + i))

export const STANDS: Stand[] = [
  ...group('10', 'Code C', ['104', '105', '106']),
  ...group('10', 'B767-300ER', ['107']),
  ...group('10', 'ATR72-600', ['108']),
  ...group('11', 'B757-200', ids(114, 117)),
  ...group('12', 'B757-200', ids(122, 125)),
  ...group('12', 'A321NEO', ['126']),
  ...group('14', 'B767-400ER', ['141']),
  ...group('14', 'A330-900NEO', ids(142, 145)),
  ...group('14', 'B777-300ER', ['146']),
  ...group('14', 'B767-300ERW', ['147']),
  ...group('20', 'Code C', ['200']),
  ...group('20', 'B747-400', ['201']),
  ...group('20', 'Code C', ['202', '203']),
  ...group('20', 'Code E', ['204']),
  ...group('20', 'Code C', ['205', '206']),
  ...group('20', 'Code E', ['207']),
  ...group('20', 'Code C', ['208']),
  ...group('20', 'B737-900', ['209']),
  ...group('22', 'B737-800', ['221']),
  ...group('22', 'Code C', ids(222, 225)),
  ...group('30', 'Code C', ['301', '302']),
  ...group('40', 'A310-300', ['401']),
  ...group('40', 'B757-200W', ['402']),
  ...group('40', 'Code C', ['403']),
  ...group('40', 'B747-400', ['404']),
  ...group('40', 'Code C', ['405']),
  ...group('41', 'Code C', ['411']),
  ...group('41', 'Code F', ['412']),
  ...group('41', 'Code C', ['413', '414']),
  ...group('41', 'B747-400', ['415']),
  ...group('41', 'A321-200', ['416']),
  ...group('42', 'A321-200', ['421']),
  ...group('42', 'B747-400', ['422']),
  ...group('42', 'B737-800', ['423']),
  ...group('42', 'Code C', ['424']),
  ...group('42', 'AN124-100', ['425']),
  ...group('42', 'Code C', ['426']),
  ...group('50', 'Code C', ['501']),
  ...group('50', 'Code D', ['502']),
  ...group('50', 'B777-200', ['503']),
  ...group('50', 'B747-400', ['504']),
  ...group('50', 'A330-900NEO', ['505']),
  ...group('50', 'B757-300W', ['506']),
  ...group('60', 'Code C', ['600', '601']),
  ...group('60', 'A330-300', ['602']),
  ...group('60', 'Code C', ['603', '604']),
  ...group('60', 'B747-400', ['605']),
  ...group('60', 'Code C', ['606', '607']),
  ...group('60', 'B747-400', ['608']),
  ...group('60', 'Code C', ['609']),
  ...group('70', 'E195 LR', ids(701, 703)),
  ...group('70', 'ATR72-600', ids(704, 706)),
  ...group('80', 'B767-300ERW', ['801']),
  ...group('80', 'B767-300ER', ['802', '803']),
  ...group('80', 'A321-200', ids(804, 806)),
  ...group('Temporária', 'Code E', ['351']),
]

const aircraft = (code: string, label: string, wingspanM: number): AircraftType => ({
  code,
  label,
  wingspanM,
  category: categoryOf(wingspanM),
})

/** Types offered in the form. Wingspans are manufacturer figures typed in by us, to be confirmed. */
export const AIRCRAFT: AircraftType[] = [
  aircraft('ATR72', 'ATR 72-600', 27.05),
  aircraft('E190', 'Embraer 190', 28.72),
  aircraft('A320', 'Airbus A320', 35.8),
  aircraft('A321', 'Airbus A321', 35.8),
  aircraft('B738', 'Boeing 737-800', 35.8),
  aircraft('B752', 'Boeing 757-200', 38.05),
  aircraft('B763', 'Boeing 767-300ER', 47.57),
  aircraft('A333', 'Airbus A330-300', 60.3),
  aircraft('B788', 'Boeing 787-8', 60.12),
  aircraft('B744', 'Boeing 747-400', 64.4),
  aircraft('B77W', 'Boeing 777-300ER', 64.8),
]
