// Compact grammar for one committed ordered answer. Prefixes never reach the game.
import { validSelection } from "./engine-selection-cursor-v1.mjs";
export const PLAN="factorized_ordered_card_answer_v1";
export function largeDomain(n,min,max,cancelable,limit=512){
  if(!Number.isSafeInteger(n)||n<0||!Number.isSafeInteger(min)||min<0||!Number.isSafeInteger(max)||max<min||min>n||typeof cancelable!=="boolean")throw Error("Invalid ordered answer domain");
  let count=Number(cancelable),permutations=1;
  for(let k=0;k<=Math.min(max,n);k++){
    if(k>=min)count+=permutations;
    if(count>limit)return true;
    permutations*=n-k;
  }
  return false;
}
export class OrderedAnswerPlanner {
  constructor(){this.active=null;}
  observe(state){
    if(state?.type!=="decision")return state;
    if(state.decision!=="card_select" || state.generated_choice_presentation!=null){this.active=null;return state;}
    if(!validSelection(state))throw Error("Incomplete native ordered answer source");
    if(!largeDomain(state.cards.length,state.min_select,state.max_select,state.cancelable)){this.active=null;return state;}
    if(this.active){
      if(JSON.stringify(this.active.state)!==JSON.stringify(state))throw Error("Native selection changed during answer planning");
    }else this.active={state:structuredClone(state),selected:[]};
    return this.view();
  }
  view(){
    if(!this.active)throw Error("No ordered answer pending");
    return {...this.active.state,answer_plan:{contract:PLAN,selected:[...this.active.selected]}};
  }
  handle(request){
    if(request.cmd!=="action")return null;
    if(!String(request.action).startsWith("ordered_answer_")){
      if(this.active?.selected.length)throw Error("Cannot interleave native actions with an unfinished answer");
      this.active=null;
      return null;
    }
    if(!this.active)throw Error("No pending ordered answer");
    const {state,selected}=this.active,args=request.args??{};
    if(args.selection_ref!==state.selection_ref||args.prefix!==selected.join(","))throw Error("Stale ordered answer owner or prefix");
    const before=[...selected];
    if(request.action==="ordered_answer_append"){
      if(!Number.isSafeInteger(args.index)||args.index<0||args.index>=state.cards.length||selected.includes(args.index)||selected.length>=Math.min(state.max_select,state.cards.length))throw Error("Invalid ordered answer append");
      selected.push(args.index);
      return {local:true,response:this.view(),before,after:[...selected]};
    }
    let native;
    if(request.action==="ordered_answer_commit"){
      if(selected.length<state.min_select||selected.length>state.max_select)throw Error("Native answer bounds not met");
      native={cmd:"action",action:"select_cards",args:{selection_ref:state.selection_ref,indices:selected.join(",")}};
    }else if(request.action==="ordered_answer_cancel"&&state.cancelable){
      native={cmd:"action",action:"skip_select",args:{selection_ref:state.selection_ref}};
    }else throw Error("Unadvertised ordered answer completion");
    this.active=null;
    return {local:false,native,before,after:[]};
  }
}
