from simpy import PriorityResource
from simpy.resources.resource import Preempted


class PreemptionFirstResource(PriorityResource):

    def _do_put(self, event):

        if len(self.users) >= self.capacity and event.preempt:

            # Check if we can preempt another process
            preemptable = max(self.users, key=lambda e: e.key)

            if preemptable.key >= event.key:

                self.users.remove(preemptable)
                preemptable.proc.interrupt(
                    Preempted(by=event.proc, usage_since=preemptable.time,
                              resource=self)
                )

        return super(PreemptionFirstResource, self)._do_put(event)
