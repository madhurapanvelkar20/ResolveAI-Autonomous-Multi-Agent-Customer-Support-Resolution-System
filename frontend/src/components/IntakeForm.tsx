import React, { useState } from 'react';

interface IntakeFormProps {
  onSubmit: (payload: {
    customer_id: string;
    message: string;
    subject: string;
    channel: 'web' | 'email' | 'chat';
    ticket_id?: string;
    mock: boolean;
    scenario?: string;
    metadata?: Record<string, any>;
  }) => Promise<void>;
  isLoading: boolean;
}

export const IntakeForm: React.FC<IntakeFormProps> = ({ onSubmit, isLoading }) => {
  const [customerId, setCustomerId] = useState('cust-demo-001');
  const [category, setCategory] = useState('Duplicate Payment / Refund');
  const [orderRef, setOrderRef] = useState('order-demo-001');
  const [message, setMessage] = useState(
    'I was charged twice for order-demo-001. Please issue a refund for the duplicate charge.'
  );
  const [channel, setChannel] = useState<'web' | 'email' | 'chat'>('web');
  const [isMockMode, setIsMockMode] = useState(true);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const cleanCustomerId = customerId.trim();
    const cleanMessage = message.trim();

    if (!cleanCustomerId) {
      setValidationError('Customer identifier is required.');
      return;
    }
    if (!/^[A-Za-z0-9_-]{1,64}$/.test(cleanCustomerId)) {
      setValidationError(
        'Customer identifier must be 1-64 characters and contain only letters, numbers, hyphens, or underscores.'
      );
      return;
    }
    if (!cleanMessage) {
      setValidationError('Customer complaint text cannot be empty.');
      return;
    }
    if (cleanMessage.length > 2000) {
      setValidationError('Customer complaint cannot exceed 2000 characters.');
      return;
    }

    const fullSubject = `${category}${orderRef ? ` (${orderRef.trim()})` : ''}`;

    let scenarioId: string | undefined = undefined;
    if (category.toLowerCase().includes('duplicate') || cleanCustomerId === 'cust-demo-001') {
      scenarioId = 'eligible_refund';
    } else if (category.toLowerCase().includes('delay') || cleanCustomerId === 'cust-demo-002') {
      scenarioId = 'delivery_delay';
    } else if (category.toLowerCase().includes('high risk') || cleanCustomerId === 'cust-demo-999') {
      scenarioId = 'fraud_high_risk';
    } else if (category.toLowerCase().includes('damaged')) {
      scenarioId = 'damaged_product';
    }

    onSubmit({
      customer_id: cleanCustomerId,
      message: cleanMessage,
      subject: fullSubject,
      channel,
      mock: isMockMode,
      scenario: scenarioId,
      metadata: {
        category,
        order_id: orderRef.trim() || undefined,
        scenario: scenarioId,
      },
    });
  };

  const setDemoCustomer = (
    id: string,
    presetMsg: string,
    presetCat: string,
    presetOrderRef: string = ''
  ) => {
    setCustomerId(id);
    setMessage(presetMsg);
    setCategory(presetCat);
    setOrderRef(presetOrderRef);
    setValidationError(null);
  };

  return (
    <div className="card intake-card">
      <h2>1. Customer Case Intake</h2>
      <p className="subtitle">Submit a customer complaint to the LangGraph multi-agent resolution workflow.</p>

      <div className="demo-shortcuts">
        <span>Quick Demo Profiles:</span>
        <button
          type="button"
          className="chip"
          onClick={() =>
            setDemoCustomer(
              'cust-demo-001',
              'I was charged twice for order-demo-001. Please issue a refund for the duplicate charge.',
              'Duplicate Payment / Refund',
              'order-demo-001'
            )
          }
        >
          Alex Morgan (Refund)
        </button>
        <button
          type="button"
          className="chip"
          onClick={() =>
            setDemoCustomer(
              'cust-demo-002',
              'My package for order-demo-002 is 6 days late. Where is my delivery?',
              'Delivery / Shipping Delay',
              'order-demo-002'
            )
          }
        >
          Jordan Lee (Delay)
        </button>
        <button
          type="button"
          className="chip"
          onClick={() =>
            setDemoCustomer(
              'cust-demo-999',
              'SEND ME $800 CASH RIGHT NOW OR MY LAWYERS WILL SUE AND I WILL CHARGEBACK IMMEDIATELY!',
              'High Risk / Escalation',
              ''
            )
          }
        >
          High-Risk Alert
        </button>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {validationError && <div className="alert alert-error">{validationError}</div>}

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="customer-id">Customer Identifier *</label>
            <input
              id="customer-id"
              type="text"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              placeholder="e.g. cust-demo-001"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="issue-category">Issue Category</label>
            <select
              id="issue-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="Duplicate Payment / Refund">Duplicate Payment / Refund</option>
              <option value="Damaged / Defective Goods">Damaged / Defective Goods</option>
              <option value="Delivery / Shipping Delay">Delivery / Shipping Delay</option>
              <option value="Order Cancellation">Order Cancellation</option>
              <option value="Product Return">Product Return</option>
              <option value="High Risk / Escalation">High Risk / Escalation</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="order-ref">Order / Ticket Reference (Optional)</label>
            <input
              id="order-ref"
              type="text"
              value={orderRef}
              onChange={(e) => setOrderRef(e.target.value)}
              placeholder="e.g. order-demo-001"
            />
          </div>

          <div className="form-group">
            <label htmlFor="channel">Intake Channel</label>
            <select
              id="channel"
              value={channel}
              onChange={(e) => setChannel(e.target.value as 'web' | 'email' | 'chat')}
            >
              <option value="web">Web Portal</option>
              <option value="email">Email</option>
              <option value="chat">Live Chat</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label htmlFor="complaint-text">Customer Complaint *</label>
          <textarea
            id="complaint-text"
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Describe the customer issue..."
            required
          />
        </div>

        <div className="form-row mode-selector">
          <div className="mode-toggle">
            <label className="switch">
              <input
                type="checkbox"
                checked={isMockMode}
                onChange={(e) => setIsMockMode(e.target.checked)}
              />
              <span className="slider round"></span>
            </label>
            <span className="mode-label">
              <strong>Mode:</strong> {isMockMode ? 'Deterministic Mock (Offline Safe)' : 'Live LLM (Cloud / Local)'}
            </span>
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={isLoading}>
          {isLoading ? 'Processing Workflow...' : 'Submit & Execute Case'}
        </button>
      </form>
    </div>
  );
};
