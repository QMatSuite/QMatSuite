/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package agent;

import java.util.ArrayList;

import com.consts.Constants.EnumMixingMode;
import com.consts.Constants.EnumOccupations;
import com.consts.Constants.EnumSmearing;
import com.consts.Constants.EnumUnitEnergy;
import com.consts.Constants.ProgramName;

import app.input.geo.Element;

public class InputAgentScf extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = -3659165710616979269L;
	public Boolean setMag,
	setU,
	setHybrid,
	setVdw,
	setAdv,
	setE;
	public Boolean expandStandard,
	expandMag,
	expandU,
	expandHybrid,
	expandVdw,
	expandAdv,
	expandE;
	
	//standard
	public WrapperEnum enumOccupation;//EnumOccupations 
	public WrapperBoolean boolRestart;
	public WrapperBoolean boolForce;
	public WrapperBoolean boolStress;
	public WrapperEnum enumEnergyUnit;
	public WrapperDouble  ecutWfc,
	ecutRho,
	elecConv,
	mixBeta,
	degauss;
	public WrapperInteger nElecMaxStep,
	nkx,
	nky,
	nkz;
	public WrapperEnum enumMixing;//EnumMixingMode
	public WrapperEnum enumSmearing;//EnumSmearing
	
	//magnet
	public WrapperInteger nspin;
	public WrapperBoolean noncolin;
	public WrapperBoolean boolSoc;
	public WrapperBoolean setForElements;
	public WrapperBoolean setForAtoms;
	//hubbardU
	//public WrapperBoolean boolHubbardU;
	public WrapperBoolean lda_plus_u;
	public ArrayList<Element> elementList;
	
	public InputAgentScf() {
		super(ProgramName.PW);
		//************************|***********//
		//***********************\|/**********//
		//*******already dealt with in PwInput//
		//general
		setMag=false;setU=false;setHybrid=false;
		setVdw=false;setAdv=false;setE=false;
		expandStandard=false;expandMag=false;expandU=false;expandHybrid=false;
		expandVdw=false;expandAdv=false;expandE=false;
		//spin
		resetnspin();resetnoncolin();resetboolSoc();//ok
		setForElements=new WrapperBoolean(false);//ok
		setForAtoms = new WrapperBoolean(false);//ok
		//DFT+U
		//boolHubbardU=new WrapperBoolean(false);
		resetldaplusu();//ok
		elementList = new ArrayList<Element>();//ok, //for scfHubbard, part of all elements
		//standard
		resetboolRestart(); //false is from scratch //ok
		resetboolForce();resetboolStress();resetenumOccupation();//ok
		enumEnergyUnit = new WrapperEnum(EnumUnitEnergy.Ry);//ok
		ecutWfc = new WrapperDouble(null);//ok
		ecutRho = new WrapperDouble(null);//ok
		resetnElecMaxStep();resetelecConv();resetenumMixing();resetmixBeta();//ok
		nkx = new WrapperInteger(1);//ok
		nky = new WrapperInteger(1);//ok
		nkz = new WrapperInteger(1);//ok
		resetenumSmearing();//ok
		degauss = new WrapperDouble(0.0);//ok
		//***********************/|\*********//
		//************************|**********//
		
	}
	//hubbardU
	public boolean resetldaplusu() {boolean out = false;if(lda_plus_u==null){lda_plus_u=new WrapperBoolean(out);}else{lda_plus_u.setValue(out);}return out;}
	//spin
	public int resetnspin() {int out = 1;if(nspin==null){nspin=new WrapperInteger(out);}else{nspin.setValue(out);}return out;}
	public boolean resetnoncolin() {boolean out = false;if(noncolin==null){noncolin=new WrapperBoolean(out);}else{noncolin.setValue(out);}return out;}
	public boolean resetboolSoc() {boolean out = false;if(boolSoc==null){boolSoc=new WrapperBoolean(out);}else{boolSoc.setValue(out);}return out;}
	//standard
	public boolean resetboolRestart() {boolean out = false;if(boolRestart==null){boolRestart=new WrapperBoolean(out);}else{boolRestart.setValue(out);}return out;}
	public boolean resetboolForce() {boolean out = false;if(boolForce==null){boolForce=new WrapperBoolean(out);}else{boolForce.setValue(out);}return out;}
	public boolean resetboolStress() {boolean out = false;if(boolStress==null){boolStress=new WrapperBoolean(out);}else{boolStress.setValue(out);}return out;}
	public EnumOccupations resetenumOccupation() {EnumOccupations out = EnumOccupations.smearing;
	if(enumOccupation==null){enumOccupation=new WrapperEnum(out);}else{enumOccupation.setValue(out);}return out;}
	
	public int resetnElecMaxStep() {int out = 100;if(nElecMaxStep==null){nElecMaxStep=new WrapperInteger(out);}else{nElecMaxStep.setValue(out);}return out;}
	public double resetelecConv() {double out = 1e-6;if(elecConv==null){elecConv=new WrapperDouble(out);}else{elecConv.setValue(out);}return out;}
	public EnumMixingMode resetenumMixing() {
		EnumMixingMode out = EnumMixingMode.plain;if(enumMixing==null){enumMixing=new WrapperEnum(out);}else{enumMixing.setValue(out);}return out;}
	public double resetmixBeta() {double out = 0.7;if(mixBeta==null){mixBeta=new WrapperDouble(out);}else{mixBeta.setValue(out);}return out;}
	
	public EnumSmearing resetenumSmearing() {
		EnumSmearing out = EnumSmearing.gauss;if(enumSmearing==null){enumSmearing=new WrapperEnum(out);}else{enumSmearing.setValue(out);}return out;}
	
}
