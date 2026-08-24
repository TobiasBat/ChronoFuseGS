#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AScreenCapturer.generated.h"

UCLASS()
class CHRONOFUSEGS_API AAScreenCapturer : public AActor
{
	GENERATED_BODY()

public:
	AAScreenCapturer();

protected:
	virtual void BeginPlay() override;

public:
	virtual void Tick(float DeltaTime) override;

};
