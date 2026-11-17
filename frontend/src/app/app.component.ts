import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService } from './services/api.service';
import { AuthService } from './services/auth.service';
import { Approval, CapacityRequest, Rack, Site, User } from './models/api';

@Component({selector: 'app-root', standalone: true, imports: [CommonModule, FormsModule], templateUrl: './app.component.html'})
export class AppComponent implements OnInit {
  user(): User | null { return this.auth.user(); }
  readonly busy = signal(false);
  page = 'overview';
  registering = false;
  error = '';
  notice = '';
  sites: Site[] = [];
  racks: Rack[] = [];
  requests: CapacityRequest[] = [];
  approvals: Approval[] = [];
  email = 'approver@opspilot-demo.com';
  password = 'LocalDev123!';
  siteName = ''; city = ''; totalCapacity = 100;
  rackName = ''; rackSiteId = 0; rackSlots = 20;
  requestSiteId = 0; quantity = 1; description = '';
  constructor(private auth: AuthService, private api: ApiService) {}
  ngOnInit(): void {}
  async login(): Promise<void> { await this.run(async () => { if (this.registering) await this.auth.register(this.email, this.password); else await this.auth.login(this.email, this.password); await this.load(); }); }
  toggleRegistration(): void { this.registering = !this.registering; this.email = this.registering ? '' : 'approver@opspilot-demo.com'; this.password = this.registering ? '' : 'LocalDev123!'; }
  useDemo(role: 'engineer' | 'approver'): void {
    this.email = role === 'engineer' ? 'engineer@opspilot-demo.com' : 'approver@opspilot-demo.com';
    this.password = role === 'engineer' ? 'Engineer123!' : 'LocalDev123!';
  }
  logout(): void { this.auth.logout(); this.page = 'overview'; }
  async load(): Promise<void> {
    const [sites, racks, requests] = await Promise.all([this.api.sites(), this.api.racks(), this.api.requests()]);
    this.sites = sites; this.racks = racks; this.requests = requests;
    if (this.user()?.role === 'approver') this.approvals = await this.api.approvals();
    if (!this.rackSiteId && sites.length) this.rackSiteId = sites[0].id;
    if (!this.requestSiteId && sites.length) this.requestSiteId = sites[0].id;
  }
  async createSite(): Promise<void> { await this.run(async () => { await this.api.createSite({name: this.siteName, city: this.city, total_capacity: this.totalCapacity}); this.siteName = ''; this.city = ''; await this.load(); this.notice = 'Site added.'; }); }
  async createRack(): Promise<void> { await this.run(async () => { await this.api.createRack({site_id: Number(this.rackSiteId), name: this.rackName, total_slots: this.rackSlots}); this.rackName = ''; await this.load(); this.notice = 'Rack added.'; }); }
  async createRequest(): Promise<void> { await this.run(async () => { await this.api.createRequest({site_id: Number(this.requestSiteId), quantity: this.quantity, description: this.description}); this.description = ''; await this.load(); this.notice = 'Capacity request submitted.'; }); }
  async propose(item: CapacityRequest): Promise<void> { await this.run(async () => { await this.api.propose(item.id); await this.load(); this.notice = `A placement proposal is ready for request #${item.id}.`; }); }
  async review(item: Approval, decision: 'approve' | 'reject'): Promise<void> { await this.run(async () => { await this.api.review(item.id, decision); await this.load(); this.notice = `Proposal ${decision}d.`; }); }
  siteNameFor(id: number): string { return this.sites.find(site => site.id === id)?.name ?? `Site ${id}`; }
  usedFor(siteId: number): number { return this.racks.filter(r => r.site_id === siteId).reduce((sum, r) => sum + r.used_slots, 0); }
  totalFor(siteId: number): number { return this.racks.filter(r => r.site_id === siteId).reduce((sum, r) => sum + r.total_slots, 0); }
  percentFor(siteId: number): number { const total = this.totalFor(siteId); return total ? Math.round(100 * this.usedFor(siteId) / total) : 0; }
  totalSlots(): number { return this.racks.reduce((sum, r) => sum + r.total_slots, 0); }
  usedSlots(): number { return this.racks.reduce((sum, r) => sum + r.used_slots, 0); }
  requestDescription(id: number): string { const request = this.requests.find(item => item.id === id); return request ? `${request.quantity} servers · ${this.siteNameFor(request.site_id)}` : 'Capacity request'; }
  private async run(action: () => Promise<void>): Promise<void> {
    this.busy.set(true); this.error = ''; this.notice = '';
    try { await action(); } catch (error: unknown) {
      const response = error as {status?: number; error?: {detail?: unknown}};
      const detail = response?.error?.detail;
      if (typeof detail === 'string') {
        this.error = detail;
      } else if (Array.isArray(detail)) {
        this.error = detail.map(item => typeof item?.msg === 'string' ? item.msg : '').filter(Boolean).join(' ')
          || 'Please check the information and try again.';
      } else if (response?.status === 0) {
        this.error = 'Cannot reach OpsPilot. Check that it is running and try again.';
      } else if (typeof response?.status === 'number' && response.status >= 500) {
        this.error = `OpsPilot returned a server error (${response.status}). Check the backend log for details.`;
      } else if (typeof response?.status === 'number') {
        this.error = `The request failed (HTTP ${response.status}). Please try again.`;
      } else {
        this.error = 'Something went wrong. Please try again.';
      }
    } finally { this.busy.set(false); }
  }
}
