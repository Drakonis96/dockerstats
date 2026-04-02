# -*- coding: utf-8 -*-

import time


def _clean_text(value):
    text = str(value or '').strip()
    return text or None


def _target_label(target_type):
    return 'Stack' if str(target_type or '').strip().lower() == 'project' else 'Container'


def _format_transition(previous_version=None, new_version=None):
    previous = _clean_text(previous_version)
    new = _clean_text(new_version)
    if previous and new:
        return f'{previous} -> {new}'
    return None


def build_update_available_message(target_type, target_name, previous_version=None, new_version=None):
    label = _target_label(target_type).lower()
    name = _clean_text(target_name) or 'unknown'
    transition = _format_transition(previous_version, new_version)
    if transition:
        return f'Update available for {label} "{name}": {transition}'
    return f'Update available for {label} "{name}".'


def build_update_result_message(target_type, target_name, ok, previous_version=None, new_version=None, fallback_message=None):
    label = _target_label(target_type)
    name = _clean_text(target_name) or 'unknown'
    transition = _format_transition(previous_version, new_version)
    fallback = _clean_text(fallback_message)

    if ok:
        if transition:
            return f'{label} "{name}" updated from {transition}'
        return f'{label} "{name}" updated.'

    if transition:
        base = f'{label} "{name}" failed to update ({transition}).'
    else:
        base = f'{label} "{name}" failed to update.'
    if fallback:
        return f'{base} {fallback}'
    return base


def build_update_result_event(
    target_type,
    target_id,
    target_name,
    ok,
    history_entry=None,
    fallback_message=None,
    previous_version=None,
    new_version=None,
    timestamp=None,
):
    history = history_entry or {}
    resolved_type = 'project' if str(target_type or '').strip().lower() == 'project' else 'container'
    resolved_name = _clean_text(history.get('target_name')) or _clean_text(target_name) or _clean_text(target_id) or 'unknown'
    resolved_previous = _clean_text(history.get('previous_version')) or _clean_text(previous_version)
    resolved_new = _clean_text(history.get('new_version')) or _clean_text(new_version)
    return {
        'type': 'update',
        'scope': 'update_success' if ok else 'update_failure',
        'timestamp': float(timestamp if timestamp is not None else time.time()),
        'cid': target_id if resolved_type == 'container' else None,
        'container': resolved_name if resolved_type == 'container' else '',
        'project': resolved_name if resolved_type == 'project' else '',
        'target_type': resolved_type,
        'target_name': resolved_name,
        'previous_version': resolved_previous,
        'new_version': resolved_new,
        'msg': build_update_result_message(
            resolved_type,
            resolved_name,
            ok,
            previous_version=resolved_previous,
            new_version=resolved_new,
            fallback_message=fallback_message,
        ),
    }