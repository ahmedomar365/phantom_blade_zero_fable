// Difficulty presets. `T` is the live tuning the hero and boss read; setDiff() switches preset.
export const DIFFS = {
  standard: {
    label: 'Disciple', parry: 0.20, circle: 0.32, iframe: [0.0, 0.30], bossDmg: 1.0, blockCost: 0.8, chip: 0.12, breakDmg: 0.4,
    thinkP1: [0.7, 1.4], thinkP2: [0.25, 0.7], speedVar: 0, bossHp: 2200, postDecay: 7, postDelay: 4, parryPost: 1.0,
    guardP1: [3, 4], guardP2: [2, 3], punishHeal: false, retryP2: true, healAmt: 45, heals: 3, qiRegen: 9, hitInv: 0.45, mash: 0,
  },
  master: {
    // tight timing, heavy hits, no breathing room: three or four mistakes end the duel, and death starts it over
    label: 'Master', parry: 0.13, circle: 0.19, iframe: [0.02, 0.21], bossDmg: 1.65, blockCost: 1.3, chip: 0.22, breakDmg: 0.75,
    thinkP1: [0.3, 0.8], thinkP2: [0.08, 0.38], speedVar: 0.17, bossHp: 2600, postDecay: 12, postDelay: 2.8, parryPost: 0.8,
    guardP1: [2, 3], guardP2: [2, 2], punishHeal: true, retryP2: false, healAmt: 38, heals: 3, qiRegen: 7, hitInv: 0.3, mash: 0.17,
  },
};
export const T = Object.assign({ name: 'master' }, DIFFS.master);
export function setDiff(name) { if (!DIFFS[name]) name = 'master'; Object.assign(T, DIFFS[name], { name }); return T; }
export const rndIn = (r) => r[0] + Math.random() * (r[1] - r[0]);
