'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  socialService,
  type SocialStats,
  type SocialMessage,
  type SocialPost,
  type SocialContact,
  type Campaign,
  type ScheduledItem,
} from '@/services/social';
import {
  MessageCircle, Facebook, Send, Clock, Users, Megaphone,
  Loader2, RefreshCw, Plus, CheckCircle2, XCircle, Bot,
  CalendarClock, BarChart3, UserPlus,
} from 'lucide-react';

type Tab = 'whatsapp' | 'facebook' | 'campaigns';

export default function SocialPage() {
  const [tab, setTab] = React.useState<Tab>('whatsapp');
  const [stats, setStats] = React.useState<SocialStats | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [message, setMessage] = React.useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const fetchStats = React.useCallback(async () => {
    try {
      const data = await socialService.getStats();
      setStats(data);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { fetchStats(); }, [fetchStats]);

  const showMsg = (text: string, type: 'success' | 'error' = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Social Automation</h1>
          <p className="text-muted-foreground">WhatsApp & Facebook bots with AI-powered responses</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => { setLoading(true); fetchStats(); }}>
          <RefreshCw className="mr-2 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Feedback */}
      {message && (
        <div className={`rounded-lg border p-3 flex items-center gap-2 ${message.type === 'success' ? 'border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400' : 'border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400'}`}>
          {message.type === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
          <span className="text-sm">{message.text}</span>
        </div>
      )}

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{stats?.total_contacts ?? 0}</p>
              <p className="text-sm text-muted-foreground">Contacts</p>
            </div>
            <Users className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{stats?.whatsapp_messages ?? 0}</p>
              <p className="text-sm text-muted-foreground">WA Messages</p>
            </div>
            <MessageCircle className="h-5 w-5 text-green-500" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{stats?.facebook_posts ?? 0}</p>
              <p className="text-sm text-muted-foreground">FB Posts</p>
            </div>
            <Facebook className="h-5 w-5 text-blue-500" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{stats?.pending_scheduled ?? 0}</p>
              <p className="text-sm text-muted-foreground">Scheduled</p>
            </div>
            <CalendarClock className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold">{stats?.active_campaigns ?? 0}</p>
              <p className="text-sm text-muted-foreground">Campaigns</p>
            </div>
            <Megaphone className="h-5 w-5 text-muted-foreground" />
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b">
        {([
          { key: 'whatsapp' as const, label: 'WhatsApp Bot', icon: MessageCircle },
          { key: 'facebook' as const, label: 'Facebook Bot', icon: Facebook },
          { key: 'campaigns' as const, label: 'Campaigns', icon: Megaphone },
        ]).map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'whatsapp' && <WhatsAppTab onMsg={showMsg} />}
      {tab === 'facebook' && <FacebookTab onMsg={showMsg} />}
      {tab === 'campaigns' && <CampaignsTab onMsg={showMsg} />}
    </div>
  );
}

/* ─── WhatsApp Tab ─────────────────────────────────────── */

function WhatsAppTab({ onMsg }: { onMsg: (text: string, type?: 'success' | 'error') => void }) {
  const [messages, setMessages] = React.useState<SocialMessage[]>([]);
  const [scheduled, setScheduled] = React.useState<ScheduledItem[]>([]);
  const [contacts, setContacts] = React.useState<SocialContact[]>([]);
  const [loadingMsgs, setLoadingMsgs] = React.useState(true);

  // Send form
  const [to, setTo] = React.useState('');
  const [msgText, setMsgText] = React.useState('');
  const [autoReply, setAutoReply] = React.useState(false);
  const [sending, setSending] = React.useState(false);

  // Schedule form
  const [showSchedule, setShowSchedule] = React.useState(false);
  const [schedTo, setSchedTo] = React.useState('');
  const [schedMsg, setSchedMsg] = React.useState('');
  const [schedAt, setSchedAt] = React.useState('');

  // Add contact
  const [showAddContact, setShowAddContact] = React.useState(false);
  const [newContact, setNewContact] = React.useState({ name: '', identifier: '' });

  const fetchAll = React.useCallback(async () => {
    try {
      const [msgData, schedData, contactData] = await Promise.all([
        socialService.whatsappMessages(),
        socialService.whatsappScheduled(),
        socialService.listContacts('whatsapp'),
      ]);
      setMessages(msgData.messages || []);
      setScheduled(schedData.scheduled || []);
      setContacts(contactData.contacts || []);
    } catch {
      /* ignore */
    } finally {
      setLoadingMsgs(false);
    }
  }, []);

  React.useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleSend = async () => {
    if (!to.trim() || !msgText.trim()) return;
    setSending(true);
    try {
      await socialService.whatsappSend(to.trim(), msgText.trim(), autoReply);
      onMsg('Message sent');
      setTo('');
      setMsgText('');
      fetchAll();
    } catch {
      onMsg('Send failed', 'error');
    } finally {
      setSending(false);
    }
  };

  const handleSchedule = async () => {
    if (!schedTo.trim() || !schedMsg.trim() || !schedAt) return;
    try {
      await socialService.whatsappSchedule({ to: schedTo.trim(), message: schedMsg.trim(), scheduled_at: schedAt });
      onMsg('Message scheduled');
      setShowSchedule(false);
      setSchedTo('');
      setSchedMsg('');
      setSchedAt('');
      fetchAll();
    } catch {
      onMsg('Schedule failed', 'error');
    }
  };

  const handleAddContact = async () => {
    if (!newContact.name.trim() || !newContact.identifier.trim()) return;
    try {
      await socialService.addContact({ name: newContact.name.trim(), platform: 'whatsapp', identifier: newContact.identifier.trim() });
      onMsg('Contact added');
      setShowAddContact(false);
      setNewContact({ name: '', identifier: '' });
      fetchAll();
    } catch {
      onMsg('Failed to add contact', 'error');
    }
  };

  if (loadingMsgs) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-4">
      {/* Send Message */}
      <Card>
        <CardHeader><CardTitle className="text-base">Send WhatsApp Message</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>To (phone number)</Label>
              <Input value={to} onChange={(e) => setTo(e.target.value)} placeholder="+880..." />
            </div>
            <div className="flex items-end gap-2">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={autoReply} onChange={(e) => setAutoReply(e.target.checked)} className="rounded" />
                <Bot className="h-4 w-4" /> AI Auto-Reply
              </label>
            </div>
          </div>
          <Textarea value={msgText} onChange={(e) => setMsgText(e.target.value)} placeholder="Type your message..." rows={2} />
          <div className="flex gap-2">
            <Button onClick={handleSend} disabled={sending || !to.trim() || !msgText.trim()}>
              {sending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Send
            </Button>
            <Button variant="outline" onClick={() => setShowSchedule(!showSchedule)}>
              <Clock className="mr-2 h-4 w-4" /> Schedule
            </Button>
            <Button variant="outline" onClick={() => setShowAddContact(!showAddContact)}>
              <UserPlus className="mr-2 h-4 w-4" /> Add Contact
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Schedule Form */}
      {showSchedule && (
        <Card>
          <CardHeader><CardTitle className="text-base">Schedule Message</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              <div><Label>To</Label><Input value={schedTo} onChange={(e) => setSchedTo(e.target.value)} placeholder="+880..." /></div>
              <div><Label>Message</Label><Input value={schedMsg} onChange={(e) => setSchedMsg(e.target.value)} placeholder="Message text" /></div>
              <div><Label>Schedule At</Label><Input type="datetime-local" value={schedAt} onChange={(e) => setSchedAt(e.target.value)} /></div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleSchedule} disabled={!schedTo.trim() || !schedMsg.trim() || !schedAt}>
                <CalendarClock className="mr-2 h-4 w-4" /> Schedule
              </Button>
              <Button variant="outline" onClick={() => setShowSchedule(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Add Contact Form */}
      {showAddContact && (
        <Card>
          <CardHeader><CardTitle className="text-base">Add WhatsApp Contact</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2">
              <div><Label>Name</Label><Input value={newContact.name} onChange={(e) => setNewContact({ ...newContact, name: e.target.value })} placeholder="Contact name" /></div>
              <div><Label>Phone Number</Label><Input value={newContact.identifier} onChange={(e) => setNewContact({ ...newContact, identifier: e.target.value })} placeholder="+880..." /></div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleAddContact} disabled={!newContact.name.trim() || !newContact.identifier.trim()}>
                <UserPlus className="mr-2 h-4 w-4" /> Add
              </Button>
              <Button variant="outline" onClick={() => setShowAddContact(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {/* Contacts */}
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Users className="h-4 w-4" /> Contacts ({contacts.length})</CardTitle></CardHeader>
          <CardContent>
            {contacts.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No contacts yet</p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {contacts.map((c) => (
                  <div key={c.id} className="flex items-center justify-between text-sm py-1">
                    <span className="font-medium">{c.name}</span>
                    <span className="text-xs text-muted-foreground font-mono">{c.identifier}</span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Scheduled */}
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Clock className="h-4 w-4" /> Scheduled ({scheduled.length})</CardTitle></CardHeader>
          <CardContent>
            {scheduled.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No scheduled messages</p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {scheduled.map((s) => (
                  <div key={s.id} className="text-sm py-1 border-b last:border-0">
                    <div className="flex justify-between">
                      <Badge variant="outline" className="text-xs">{s.action_type}</Badge>
                      <span className="text-xs text-muted-foreground">{new Date(s.scheduled_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Message History */}
      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><MessageCircle className="h-4 w-4" /> Recent Messages</CardTitle></CardHeader>
        <CardContent>
          {messages.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No messages yet</p>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {messages.map((m) => (
                <div key={m.id} className={`rounded-lg p-3 text-sm ${m.direction === 'outgoing' ? 'bg-primary/10 ml-8' : 'bg-muted mr-8'}`}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs font-medium">{m.direction === 'outgoing' ? 'Sent' : 'Received'} → {m.contact_identifier}</span>
                    <Badge variant="outline" className="text-xs">{m.status}</Badge>
                  </div>
                  <p>{m.content}</p>
                  <p className="text-xs text-muted-foreground mt-1">{new Date(m.created_at).toLocaleString()}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Facebook Tab ─────────────────────────────────────── */

function FacebookTab({ onMsg }: { onMsg: (text: string, type?: 'success' | 'error') => void }) {
  const [posts, setPosts] = React.useState<SocialPost[]>([]);
  const [scheduled, setScheduled] = React.useState<ScheduledItem[]>([]);
  const [loadingPosts, setLoadingPosts] = React.useState(true);

  // Post form
  const [content, setContent] = React.useState('');
  const [imageUrl, setImageUrl] = React.useState('');
  const [aiGenerate, setAiGenerate] = React.useState(false);
  const [prompt, setPrompt] = React.useState('');
  const [scheduleAt, setScheduleAt] = React.useState('');
  const [posting, setPosting] = React.useState(false);

  const fetchAll = React.useCallback(async () => {
    try {
      const [postData, schedData] = await Promise.all([
        socialService.facebookPosts(),
        socialService.facebookScheduled(),
      ]);
      setPosts(postData.posts || []);
      setScheduled(schedData.scheduled || []);
    } catch {
      /* ignore */
    } finally {
      setLoadingPosts(false);
    }
  }, []);

  React.useEffect(() => { fetchAll(); }, [fetchAll]);

  const handlePost = async () => {
    if (!aiGenerate && !content.trim()) return;
    if (aiGenerate && !prompt.trim()) return;
    setPosting(true);
    try {
      const res = await socialService.facebookPost({
        content: content.trim() || undefined,
        prompt: aiGenerate ? prompt.trim() : undefined,
        ai_generate: aiGenerate,
        image_url: imageUrl.trim() || undefined,
        schedule_at: scheduleAt || undefined,
      });
      onMsg(scheduleAt ? 'Post scheduled' : `Post ${res.status}`);
      setContent('');
      setPrompt('');
      setImageUrl('');
      setScheduleAt('');
      fetchAll();
    } catch {
      onMsg('Post failed', 'error');
    } finally {
      setPosting(false);
    }
  };

  if (loadingPosts) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-4">
      {/* Create Post */}
      <Card>
        <CardHeader><CardTitle className="text-base">Create Facebook Post</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={aiGenerate} onChange={(e) => setAiGenerate(e.target.checked)} className="rounded" />
            <Bot className="h-4 w-4" /> AI-Generate Content
          </label>

          {aiGenerate ? (
            <div>
              <Label>AI Prompt</Label>
              <Textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="Describe the post you want AI to generate..." rows={3} />
            </div>
          ) : (
            <div>
              <Label>Post Content</Label>
              <Textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your post..." rows={3} />
            </div>
          )}

          <div className="grid gap-3 md:grid-cols-2">
            <div>
              <Label>Image URL (optional)</Label>
              <Input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="https://..." />
            </div>
            <div>
              <Label>Schedule (optional)</Label>
              <Input type="datetime-local" value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)} />
            </div>
          </div>

          <Button onClick={handlePost} disabled={posting || (aiGenerate ? !prompt.trim() : !content.trim())}>
            {posting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
            {scheduleAt ? 'Schedule Post' : 'Publish Now'}
          </Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Scheduled */}
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Clock className="h-4 w-4" /> Scheduled Posts ({scheduled.length})</CardTitle></CardHeader>
          <CardContent>
            {scheduled.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No scheduled posts</p>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {scheduled.map((s) => (
                  <div key={s.id} className="text-sm py-2 border-b last:border-0">
                    <div className="flex justify-between">
                      <Badge variant="outline" className="text-xs">{s.action_type}</Badge>
                      <span className="text-xs text-muted-foreground">{new Date(s.scheduled_at).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Stats */}
        <Card>
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><BarChart3 className="h-4 w-4" /> Post Stats</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm">Total Posts</span>
                <span className="text-lg font-bold">{posts.length}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Published</span>
                <span className="font-medium">{posts.filter(p => p.status === 'published').length}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm">Draft</span>
                <span className="font-medium">{posts.filter(p => p.status === 'draft').length}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Posts List */}
      <Card>
        <CardHeader><CardTitle className="text-base flex items-center gap-2"><Facebook className="h-4 w-4" /> Recent Posts</CardTitle></CardHeader>
        <CardContent>
          {posts.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-6">No posts yet</p>
          ) : (
            <div className="space-y-3 max-h-80 overflow-y-auto">
              {posts.map((p) => (
                <div key={p.id} className="rounded-lg border p-3 text-sm">
                  <div className="flex justify-between mb-2">
                    <Badge variant={p.status === 'published' ? 'default' : 'secondary'}>{p.status}</Badge>
                    <span className="text-xs text-muted-foreground">{new Date(p.created_at).toLocaleString()}</span>
                  </div>
                  <p className="line-clamp-3">{p.content}</p>
                  {p.image_url && <p className="text-xs text-blue-500 mt-1 truncate">{p.image_url}</p>}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

/* ─── Campaigns Tab ────────────────────────────────────── */

function CampaignsTab({ onMsg }: { onMsg: (text: string, type?: 'success' | 'error') => void }) {
  const [campaigns, setCampaigns] = React.useState<Campaign[]>([]);
  const [loadingCampaigns, setLoadingCampaigns] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [creating, setCreating] = React.useState(false);
  const [newCampaign, setNewCampaign] = React.useState({ name: '', platform: 'whatsapp', campaign_type: 'broadcast' });

  const fetchCampaigns = React.useCallback(async () => {
    try {
      const data = await socialService.listCampaigns();
      setCampaigns(data.campaigns || []);
    } catch {
      /* ignore */
    } finally {
      setLoadingCampaigns(false);
    }
  }, []);

  React.useEffect(() => { fetchCampaigns(); }, [fetchCampaigns]);

  const handleCreate = async () => {
    if (!newCampaign.name.trim()) return;
    setCreating(true);
    try {
      await socialService.createCampaign(newCampaign);
      onMsg('Campaign created');
      setNewCampaign({ name: '', platform: 'whatsapp', campaign_type: 'broadcast' });
      setShowCreate(false);
      fetchCampaigns();
    } catch {
      onMsg('Failed to create campaign', 'error');
    } finally {
      setCreating(false);
    }
  };

  if (loadingCampaigns) {
    return <div className="flex justify-center py-12"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="mr-2 h-4 w-4" /> New Campaign
        </Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader><CardTitle className="text-base">Create Campaign</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <Label>Campaign Name</Label>
                <Input value={newCampaign.name} onChange={(e) => setNewCampaign({ ...newCampaign, name: e.target.value })} placeholder="e.g. Weekly Update" />
              </div>
              <div>
                <Label>Platform</Label>
                <select value={newCampaign.platform} onChange={(e) => setNewCampaign({ ...newCampaign, platform: e.target.value })} className="w-full border rounded px-3 py-2 text-sm bg-background">
                  <option value="whatsapp">WhatsApp</option>
                  <option value="facebook">Facebook</option>
                </select>
              </div>
              <div>
                <Label>Type</Label>
                <select value={newCampaign.campaign_type} onChange={(e) => setNewCampaign({ ...newCampaign, campaign_type: e.target.value })} className="w-full border rounded px-3 py-2 text-sm bg-background">
                  <option value="broadcast">Broadcast</option>
                  <option value="drip">Drip</option>
                  <option value="engagement">Engagement</option>
                </select>
              </div>
            </div>
            <div className="flex gap-2">
              <Button onClick={handleCreate} disabled={creating || !newCampaign.name.trim()}>
                {creating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create
              </Button>
              <Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {campaigns.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Megaphone className="h-12 w-12 mx-auto mb-4 opacity-40" />
            <p>No campaigns yet. Create one to get started.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {campaigns.map((c) => (
            <Card key={c.id}>
              <CardContent className="py-4">
                <div className="flex items-center gap-3">
                  <Megaphone className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate">{c.name}</p>
                    <p className="text-sm text-muted-foreground">{c.campaign_type} · {new Date(c.created_at).toLocaleDateString()}</p>
                  </div>
                  <Badge variant={c.platform === 'whatsapp' ? 'default' : 'secondary'}>
                    {c.platform === 'whatsapp' ? <MessageCircle className="mr-1 h-3 w-3" /> : <Facebook className="mr-1 h-3 w-3" />}
                    {c.platform}
                  </Badge>
                  <Badge variant={c.status === 'running' ? 'default' : c.status === 'completed' ? 'outline' : 'secondary'}>
                    {c.status}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
