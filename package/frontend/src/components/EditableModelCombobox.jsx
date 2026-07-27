import React, { useEffect, useMemo, useState } from 'react';
import { Check, ChevronDown } from 'lucide-react';

const uniqueModelNames = (values) => (
  [...new Set((values || []).map((value) => String(value || '').trim()).filter(Boolean))]
);

const EditableModelCombobox = ({
  id,
  value,
  options,
  onChange,
  placeholder,
  required = false,
  label = '模型',
  inputClassName = 'aurora-input',
  autoOpenOnOptions = false,
}) => {
  const [open, setOpen] = useState(false);
  const discoveredOptions = useMemo(() => uniqueModelNames(options), [options]);
  const mergedOptions = useMemo(
    () => uniqueModelNames([value, ...discoveredOptions]),
    [value, discoveredOptions],
  );
  const optionSignature = discoveredOptions.join('\u0000');
  const listboxId = `${id}-options`;

  useEffect(() => {
    if (!discoveredOptions.length) {
      setOpen(false);
      return;
    }
    if (autoOpenOnOptions) {
      setOpen(true);
    }
  }, [autoOpenOnOptions, discoveredOptions.length, optionSignature]);

  const closeWhenFocusLeaves = (event) => {
    if (!event.currentTarget.contains(event.relatedTarget)) {
      setOpen(false);
    }
  };

  const selectModel = (modelName) => {
    onChange(modelName);
    setOpen(false);
  };

  return (
    <div
      className={`aurora-model-combobox ${open ? 'is-open' : ''}`}
      onBlur={closeWhenFocusLeaves}
    >
      <div className="aurora-model-combobox-control">
        <input
          id={id}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onFocus={() => discoveredOptions.length && setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === 'ArrowDown' && discoveredOptions.length) {
              event.preventDefault();
              setOpen(true);
            } else if (event.key === 'Escape') {
              setOpen(false);
            }
          }}
          placeholder={placeholder}
          className={inputClassName}
          required={required}
          role="combobox"
          aria-label={label}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={listboxId}
        />
        <button
          type="button"
          className="aurora-model-combobox-toggle"
          onClick={() => setOpen((current) => (discoveredOptions.length ? !current : false))}
          disabled={!discoveredOptions.length}
          aria-label={discoveredOptions.length ? `展开${label}列表，已探测 ${discoveredOptions.length} 个模型` : '请先探测模型'}
          aria-expanded={open}
          aria-controls={listboxId}
          title={discoveredOptions.length ? `已探测 ${discoveredOptions.length} 个模型` : '请先点击“探测模型”'}
        >
          <ChevronDown className="h-4 w-4" />
        </button>
      </div>

      {open && discoveredOptions.length > 0 && (
        <div id={listboxId} className="aurora-model-combobox-list" role="listbox" aria-label={`${label}探测结果`}>
          <div className="aurora-model-combobox-summary">已探测 {discoveredOptions.length} 个模型，也可继续手动输入</div>
          {mergedOptions.map((modelName) => {
            const selected = modelName === value;
            const discovered = discoveredOptions.includes(modelName);
            return (
              <button
                key={modelName}
                type="button"
                role="option"
                aria-selected={selected}
                className={`aurora-model-combobox-option ${selected ? 'is-selected' : ''}`}
                onClick={() => selectModel(modelName)}
              >
                <span>{modelName}</span>
                {!discovered && <small>当前手动值</small>}
                {selected && <Check className="h-4 w-4" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default EditableModelCombobox;
