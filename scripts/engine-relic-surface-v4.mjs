import {projectRelicSurface as previous,INVENTORY_CONTRACT,ownedBeltContext} from './engine-relic-surface-v3.mjs';
import {projectAtomicSelection} from './engine-atomic-selection-v1.mjs';
import {appendPotionControls} from './engine-potion-surface-v1.mjs';
export {INVENTORY_CONTRACT};
export function projectRelicSurface(state,ctx,helpers){
 if(state.decision!=='card_select')return previous(state,ctx,helpers);
 return appendPotionControls(state,ownedBeltContext(state,ctx),helpers,projectAtomicSelection(state,ctx,helpers));
}
