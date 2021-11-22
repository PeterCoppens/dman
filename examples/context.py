from dman.persistent.context import RootContext, Context, GitContextManager, ContextCommand, command, clear
from dman.persistent.serializables import serialize, deserialize

if __name__ == '__main__':
    rt = RootContext.at_script().joinpath('_context')
    with GitContextManager(context=rt) as mgr:
        ctx = mgr.request(command(subdir='test', name='test.json'))
        rcmd = ContextCommand.from_context(ctx)
        print(rcmd)
        rctx = mgr.request(rcmd)
        print(rctx)
        print('-'*72)

        sctx = serialize(ctx, rt)
        print(sctx)
        rctx: Context = deserialize(sctx, rt)
        print(rctx)
        print(rctx.parent)
        
    with GitContextManager(context=rt) as ctx:
        ctx.request(command(name='test.dat'))
        ctx.request(command(subdir='hello'))
    
    input('press any key to clear')
    clear(rt)
