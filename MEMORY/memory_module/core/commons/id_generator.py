from core.commons.yuki import options, generator


options = options.IdGeneratorOptions(worker_id=23)
idgen = generator.DefaultIdGenerator()
idgen.set_id_generator(options)