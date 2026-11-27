// A separately versioned integration of the same lifecycle with shared identities.
import {LifecycleWorker} from "./engine-action-lifecycle-worker-v1.mjs";
import {INVENTORY_IDENTITY,projectSelectionFlows,selectionFlowReads} from "./engine-owned-inventory-identity-v1.mjs";

export class InventoryLifecycleWorker extends LifecycleWorker {
  async initialize(spec) {
    const result = await super.initialize(spec);
    // LifecycleWorker's one wrapper supplies the original surface projector.
    // Its immediate parent is the verified immutable SDK session. Reuse that
    // session with both new projection callbacks, without editing its cache.
    const Session = Object.getPrototypeOf(this.prepared.module.ManagedPlayerEnvironmentSession);
    if (!["mount","acceptNativeObservation","read"].every(name => typeof Session.prototype[name] === "function"))
      throw Error("Unexpected immutable SDK session lineage");
    this.prepared = {...this.prepared,module:{...this.prepared.module,
      ManagedPlayerEnvironmentSession: class extends Session {
        constructor(options) {
          super({...options,surfaceProjector:projectSelectionFlows,readProjector:selectionFlowReads});
        }
      }}};
    return {...result,inventory_identity_contract:INVENTORY_IDENTITY};
  }
}
