// Resolve a declared DTO scalar before same-entity views are joined. This is
// representation normalization only; different costs must still conflict.
import {createHash} from 'node:crypto';
import {stableJson} from './engine-public-input-v1.mjs';

export const CARD_COST_TYPES = 'public_visible_card_star_cost_text_v1';
const hash = value => createHash('sha256').update(stableJson(value)).digest('hex');
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const unsafe = key => ['__proto__','constructor','prototype'].includes(key);
const escape = key => String(key).replaceAll('~','~0').replaceAll('/','~1');

function starCost(value) {
  if(value === null || value === 'X') return value;
  if(Number.isSafeInteger(value) && value >= 0) return String(value);
  if(typeof value === 'string' && /^(0|[1-9][0-9]*)$/u.test(value)
      && Number.isSafeInteger(Number(value))) return value;
  throw Error('Invalid declared public card star cost');
}
function visibleCard(row) {
  return object(row) && typeof row.entity_id === 'string'
    && typeof row.definition_id === 'string' && typeof row.cost === 'string'
    && typeof row.type === 'string' && typeof row.rarity === 'string'
    && typeof row.is_upgraded === 'boolean';
}

export function normalizeCardCosts(snapshot, reads) {
  const original = {snapshot, reads}, rewrites = [];
  function walk(value, path) {
    if(Array.isArray(value)) return value.map((item,i) => walk(item, `${path}/${i}`));
    if(object(value)) {
      const result = {};
      for(const [key,item] of Object.entries(value)) {
        if(unsafe(key)) throw Error('Unsafe public scalar property');
        result[key] = walk(item, `${path}/${escape(key)}`);
      }
      if(visibleCard(value) && Object.hasOwn(value,'star_cost')) {
        const after = starCost(value.star_cost);
        if(after !== value.star_cost) {
          rewrites.push({path:`${path}/star_cost`, before:value.star_cost, after});
          result.star_cost = after;
        }
      }
      return result;
    }
    if(value === null || ['string','boolean'].includes(typeof value)
        || typeof value === 'number' && Number.isFinite(value)) return value;
    throw Error('Finite public scalar JSON required');
  }
  const normalized = walk(original,'');
  return {...normalized, evidence:{contract:CARD_COST_TYPES, original_digest:hash(original),
    normalized_digest:hash(normalized), rewrites}};
}

export function restoreCardCosts(normalized, evidence) {
  if(evidence.contract !== CARD_COST_TYPES || hash(normalized) !== evidence.normalized_digest
      || !Array.isArray(evidence.rewrites)) throw Error('Changed public scalar evidence');
  const restored = structuredClone(normalized), seen = new Set();
  for(const row of evidence.rewrites) {
    if(typeof row.path !== 'string' || !row.path.startsWith('/') || seen.has(row.path))
      throw Error('Invalid public scalar rewrite');
    seen.add(row.path);
    const keys = row.path.slice(1).split('/').map(k=>k.replaceAll('~1','/').replaceAll('~0','~'));
    if(keys.some(unsafe)) throw Error('Unsafe public scalar path');
    const key = keys.pop(), parent = keys.reduce((value,k)=>value?.[k],restored);
    if(key !== 'star_cost' || !visibleCard(parent) || parent[key] !== row.after
        || typeof row.before !== 'number' || starCost(row.before) !== row.after)
      throw Error('Changed typed public scalar rewrite');
    parent[key] = row.before;
  }
  if(hash(restored) !== evidence.original_digest) throw Error('Public scalar reconstruction failed');
  return restored;
}
