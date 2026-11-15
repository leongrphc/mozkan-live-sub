import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from translation_backend import TranslationBackend,InferenceCancelled


class BackendTests(unittest.TestCase):
    def runtime(self,*,count=1,load_error=False,infer_error=False):
        calls=[]
        def factory(path,**options):
            calls.append(('load',options))
            if options['device']=='cuda' and load_error:
                raise RuntimeError('Missing CUDA library')
            def translate(sources,**kwargs):
                calls.append(('infer',options['device'],sources,kwargs))
                if options['device']=='cuda' and infer_error:
                    raise RuntimeError('CUDA unavailable during inference')
                return sources
            return SimpleNamespace(translate_batch=translate)
        def devices():
            calls.append(('count',))
            return count
        runtime=SimpleNamespace(Translator=factory,get_cuda_device_count=devices)
        return runtime,calls

    def test_cuda_selection_preserves_requested_inputs_and_options(self):
        runtime,calls=self.runtime()
        backend=TranslationBackend('own-model',cpu_only=False,guard=lambda:None,
                                   runtime=runtime,runtime_loader=lambda:None)
        sources=[['test','</s>']]
        self.assertIs(backend.translate_batch(sources,beam_size=1),sources)
        self.assertEqual(backend.device,'cuda')
        self.assertEqual(calls[1][1],dict(device='cuda',compute_type='float16'))
        self.assertEqual(calls[-1],('infer','cuda',sources,dict(beam_size=1)))

    def test_hud_does_not_probe_gpu_or_load_runtime(self):
        runtime,calls=self.runtime()
        backend=TranslationBackend('own-model',cpu_only=True,guard=lambda:None,
                    runtime=runtime,runtime_loader=lambda:self.fail('HUD loaded CUDA runtime'))
        self.assertEqual(backend.device,'cpu')
        self.assertEqual(calls,[('load',dict(device='cpu',compute_type='int8',inter_threads=1,intra_threads=1))])

    def test_missing_gpu_and_constructor_failure_use_cpu(self):
        for options,failed in ((dict(count=0),False),(dict(load_error=True),True)):
            runtime,calls=self.runtime(**options)
            backend=TranslationBackend('model',cpu_only=False,guard=lambda:None,
                                       runtime=runtime,runtime_loader=lambda:None)
            self.assertEqual(backend.device,'cpu')
            self.assertEqual(bool(backend.cuda_failure),failed)
            self.assertEqual(calls[-1][1]['intra_threads'],2)

    def test_inference_failure_retries_once_on_cpu_and_keeps_source(self):
        runtime,calls=self.runtime(infer_error=True)
        backend=TranslationBackend('model',cpu_only=False,guard=lambda:None,
                                   runtime=runtime,runtime_loader=lambda:None)
        sources=[['A','B']]
        self.assertIs(backend.translate_batch(sources,beam_size=1,max_decoding_length=256),sources)
        self.assertEqual(backend.device,'cpu')
        self.assertEqual(backend.fallback_count,1)
        backend.translate_batch(sources)
        self.assertEqual(sum(call[0]=='load' for call in calls),2)

    def test_canceled_gpu_failure_does_not_load_cpu_or_retry(self):
        runtime,calls=self.runtime(infer_error=True)
        backend=TranslationBackend('model',cpu_only=False,guard=lambda:None,
                                   runtime=runtime,runtime_loader=lambda:None)
        checks=[0]
        def guard():
            checks[0]+=1
            if checks[0]>1:
                raise InferenceCancelled()
        with self.assertRaises(InferenceCancelled):
            backend.translate_batch([['A']],guard=guard)
        self.assertEqual(backend.device,'cuda')
        self.assertEqual(sum(call[0]=='load' for call in calls),1)

    def test_cpu_and_invalid_input_failures_propagate_without_retry(self):
        runtime,calls=self.runtime(count=0)
        backend=TranslationBackend('model',cpu_only=False,guard=lambda:None,runtime=runtime)
        def fail(*args,**kwargs):
            raise RuntimeError('CPU failure')
        backend.translator.translate_batch=fail
        with self.assertRaisesRegex(RuntimeError,'CPU failure'):
            backend.translate_batch([['A']])
        self.assertEqual(backend.fallback_count,0)

